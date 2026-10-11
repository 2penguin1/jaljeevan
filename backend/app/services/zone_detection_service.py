import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.domain.events import ZoneEscalated
from app.domain.hazards import HazardPolicies, HazardPolicy
from app.domain.lifecycle import APPROVED, ACTIVE, WATCH, ZoneStateMachine
from app.domain.scoring import EvidenceSignal, ZoneScorer
from app.domain.zones import ZoneTypeClassifier
from app.integrations.ports import PopulationGrid
from app.services.drought_assessor import AreaDrought, DroughtAssessor
from app.models import Zone
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.indicator_repository import IndicatorRepository
from app.repositories.zone_repository import ZoneRepository

Evidence = list[tuple[uuid.UUID, EvidenceSignal, int | None]]


@dataclass
class DetectionResult:
    created: int = 0
    updated: int = 0
    active: int = 0
    watch: int = 0
    skipped_locked: list[str] = field(default_factory=list)
    events: list[ZoneEscalated] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"created": self.created, "updated": self.updated, "active": self.active, "watch": self.watch,
                "skipped_locked": self.skipped_locked, "alerts": [str(e.zone_id) for e in self.events]}


class ZoneDetectionService:
    """Turns located, classified signals into zones of any size, per hazard.

    Fine clusters (ward/village/town points) and district-wide zones (district reports or severe indicators)
    are scored, moved through the lifecycle, snapshotted for trends, and kept stable across runs.
    Raises ZoneEscalated events; it never sends notifications itself.
    """

    BUFFER_M = {"ward": 1000, "village": 1500, "town": 4000}  # half of the 2/3/8 km cluster thresholds
    MATCH_IOU = 0.3
    MATCH_DIST_M = 8000
    WINDOW = timedelta(days=30)
    WATER_WINDOW = timedelta(hours=72)
    MAX_REPORTED_POP = 5_000_000

    def __init__(self, zones: ZoneRepository, areas: AdminAreaRepository, indicators: IndicatorRepository,
                 scorer: ZoneScorer, policies: HazardPolicies, machine: ZoneStateMachine,
                 types: ZoneTypeClassifier, population: PopulationGrid | None = None,
                 drought: DroughtAssessor | None = None):
        self.population = population  # people inside a zone's own shape; None -> gazetteer fallback
        self.drought = drought        # measured drought data per taluka; None -> no footprint zones
        self.zones = zones
        self.areas = areas
        self.indicators = indicators
        self.scorer = scorer
        self.policies = policies
        self.machine = machine
        self.types = types

    def detect(self, now: datetime, hazards=None) -> DetectionResult:
        result = DetectionResult()
        selected = [self.policies.get(h) for h in hazards] if hazards else self.policies.all()
        for policy in selected:
            if not self.zones.try_lock(policy.hazard):
                result.skipped_locked.append(policy.hazard)
                continue
            taken: set[uuid.UUID] = set()
            if policy.zoning == "footprint":
                self._footprint_zones(policy, now, taken, result)
                continue
            indicators = self.indicators.latest_by_district(policy.indicator_source)
            self._fine_zones(policy, now, indicators, taken, result)
            self._district_zones(policy, now, indicators, taken, result)
            for zone in self.zones.unseen(policy.hazard, taken):
                boost = policy.boost(indicators.get(zone.district_id)) if zone.district_id else 0.0
                self._finalize(zone, [], boost, now, created=False)
        result.active = self.zones.count_status(ACTIVE)
        result.watch = self.zones.count_status(WATCH)
        self.zones.flush()
        return result

    # -- fine-grained zones ----------------------------------------------------------------------
    def _fine_zones(self, policy: HazardPolicy, now: datetime, indicators: dict, taken: set,
                    result: DetectionResult) -> None:
        for cluster in self.zones.clusters(policy.hazard, now - self.WINDOW, self.BUFFER_M):
            evidence = self.zones.evidence(cluster.confidence_by_signal())
            district = self.zones.district_at(cluster.centroid_ewkt)
            boost = policy.boost(indicators.get(district[0])) if district else 0.0
            zone = self.zones.match_fine(policy.hazard, cluster.hull_ewkt, taken, self.MATCH_IOU, self.MATCH_DIST_M)
            created = zone is None
            if created:
                zone = Zone(hazard=policy.hazard, status=WATCH, first_seen=now)
            top_mention = Counter(p.mention_text for p in cluster.points).most_common(1)[0][0]
            zone.name = f"{top_mention}, {district[1]}" if district else top_mention
            zone.zone_type = self.types.classify([{"level": p.level, "is_urban": p.is_urban,
                                                   "precision": p.precision,
                                                   "district_urban": p.district_urban} for p in cluster.points])
            zone.district_id = district[0] if district else None
            self.zones.set_shape(zone, cluster.hull_ewkt, cluster.centroid_ewkt)
            zone.population_est, zone.population_urban, zone.population_source = self._population(
                cluster.hull_ewkt.split(";", 1)[-1], {p.admin_area_id for p in cluster.points if p.admin_area_id},
                evidence)
            self._persist(zone, created, taken, result)
            self._record_event(self._finalize(zone, evidence, boost, now, created), result)

    # -- district-wide zones ---------------------------------------------------------------------
    def _district_zones(self, policy: HazardPolicy, now: datetime, indicators: dict, taken: set,
                        result: DetectionResult) -> None:
        reports = self.zones.district_evidence(policy.hazard, now - self.WINDOW)
        severe = {d for d, ind in indicators.items() if policy.boost(ind) >= 0.4}
        for district_id in set(reports) | severe:
            district = self.areas.get(district_id)
            if district is None or district.level != "district":
                continue
            zone = self.zones.district_zone(policy.hazard, district_id)
            created = zone is None
            if created:
                zone = Zone(hazard=policy.hazard, status=WATCH, zone_type="district_wide",
                            district_id=district_id, first_seen=now)
            zone.name = f"{district.name} district"
            self.zones.set_shape_from_area(zone, district_id)
            evidence = self.zones.evidence(reports.get(district_id, {}))
            zone.population_est, zone.population_urban, zone.population_source = self._population(
                self.areas.wkt(district_id), {district_id}, evidence)
            self._persist(zone, created, taken, result)
            self._record_event(self._finalize(zone, evidence, policy.boost(indicators.get(district_id)), now,
                                              created), result)

    # -- data-driven (footprint) zones --------------------------------------------------------------
    def _footprint_zones(self, policy: HazardPolicy, now: datetime, taken: set, result: DetectionResult) -> None:
        """One zone per taluka that the data flags (or that the state declared). Posts inside add evidence."""
        if self.drought is None:
            return
        self.zones.dismiss_legacy(policy.hazard)
        assessed = self.drought.assess(now)
        candidates = {a for a, d in assessed.items() if d.assessment.level != "none"}
        candidates |= set(self.zones.area_ids_with_zones(policy.hazard))
        support = self.zones.area_evidence(sorted(candidates), policy.evidence_hazards, now - self.WINDOW)
        for area_id in sorted(candidates):
            drought = assessed.get(area_id)
            level = drought.assessment.level if drought else "none"
            confidence = support.get(area_id, {})
            zone = self.zones.area_zone(policy.hazard, area_id)
            declared = drought is not None and drought.assessment.declared is not None
            if level == "none" and not declared:
                confidence = {}  # once the data clears, old posts can't keep a drought zone alive
            if zone is None and not (confidence or declared):
                continue  # dry but unreported talukas are shown by the map's footprint layer, not as zones
            created = zone is None
            if created:
                zone = Zone(hazard=policy.hazard, status=WATCH, zone_type="taluka", area_id=area_id, first_seen=now)
            area = self.areas.get(area_id)
            zone.name = f"{area.name} taluka, {area.district_name}" if area.district_name else f"{area.name} taluka"
            zone.district_id = area.parent_id
            self.zones.set_shape_from_area(zone, area_id)
            zone.population_est, zone.population_urban, zone.population_source = self._dry_population(drought, area_id)
            self._persist(zone, created, taken, result)
            evidence = self.zones.evidence(confidence)
            boost = drought.assessment.boost if drought else 0.0
            self._record_event(self._finalize(zone, evidence, boost, now, created, data_cleared=level == "none"),
                               result)

    def _dry_population(self, drought: AreaDrought | None, area_id: int) -> tuple[int | None, int | None, str | None]:
        """People living in the taluka's grid cells that meet the rainfall trigger, not the whole taluka."""
        metrics = drought.metrics if drought else {}
        if metrics.get("pop_stressed") is not None:
            urban = metrics.get("pop_stressed_urban")
            return int(metrics["pop_stressed"]), int(urban) if urban is not None else None, "worldpop_dry_areas"
        return self._population(self.areas.wkt(area_id), {area_id}, [])

    # -- shared ----------------------------------------------------------------------------------
    def _persist(self, zone: Zone, created: bool, taken: set, result: DetectionResult) -> None:
        if created:
            self.zones.add(zone)
            result.created += 1
        else:
            self.zones.flush()
            result.updated += 1
        taken.add(zone.id)

    def _finalize(self, zone: Zone, evidence: Evidence, boost: float, now: datetime,
                  created: bool, data_cleared: bool = False) -> ZoneEscalated | None:
        previous_status = zone.status
        weights = {sid: self.scorer.weight(ev, now) for sid, ev, _ in evidence}
        signals = [ev for _, ev, _ in evidence]
        score = self.scorer.score(weights.values(), boost)
        ok = self.scorer.evidence_ok(signals, boost)
        # footprint zones resolve when the data clears (nobody reports "water arrived" for a drought)
        relief_seen = data_cleared or self.zones.water_arrived(weights, now - self.WATER_WINDOW)
        status, since = self.machine.next(zone.status, score, ok, zone.below_resolve_since, now, relief_seen)
        zone.score, zone.status, zone.below_resolve_since = score, status, since
        zone.independent_sources = self.scorer.independent_sources(signals)
        if evidence:
            zone.last_seen = now
        self.zones.replace_signals(zone.id, weights)
        self.zones.snapshot(zone.id, now, score, len(evidence))
        current = self.zones.average_score(zone.id, now - timedelta(days=7), now)
        previous = self.zones.average_score(zone.id, now - timedelta(days=14), now - timedelta(days=7))
        zone.trend = self.scorer.trend(current if current is not None else score, previous, created)
        live = (ACTIVE, APPROVED)
        newly_live = status in live and previous_status not in live  # e.g. watch -> active on a later run
        escalating = zone.trend in ("new", "escalating") or newly_live
        if escalating and status in live and score >= self.scorer.config.alert_score:
            return ZoneEscalated(zone.id, zone.hazard, zone.name, score, zone.trend, status)
        return None

    @staticmethod
    def _record_event(event: ZoneEscalated | None, result: DetectionResult) -> None:
        if event is not None:
            result.events.append(event)

    def _population(self, wkt: str | None, area_ids: set[int],
                    evidence: Evidence) -> tuple[int | None, int | None, str | None]:
        """(people, of whom urban, source). The population grid counts people inside the zone's own shape;
        the gazetteer (whole named places) and numbers quoted in posts are fallbacks only."""
        counted = self.population.count(wkt) if self.population is not None and wkt else None
        if counted is not None and counted.total > 0:
            return counted.total, counted.urban, "worldpop"
        total = self.zones.population_of(area_ids)
        if total > 0:
            return total, None, "gazetteer"
        reported = max((people or 0 for _, _, people in evidence), default=0)
        return (min(reported, self.MAX_REPORTED_POP), None, "reported") if reported else (None, None, None)
