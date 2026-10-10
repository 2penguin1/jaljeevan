import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.domain.events import ZoneEscalated
from app.domain.hazards import HazardPolicies, HazardPolicy
from app.domain.lifecycle import APPROVED, ACTIVE, WATCH, ZoneStateMachine
from app.domain.scoring import EvidenceSignal, ZoneScorer
from app.domain.zones import ZoneTypeClassifier
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
                 types: ZoneTypeClassifier):
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
            indicators = self.indicators.latest_by_district(policy.indicator_source)
            taken: set[uuid.UUID] = set()
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
                                                   "precision": p.precision} for p in cluster.points])
            zone.district_id = district[0] if district else None
            self.zones.set_shape(zone, cluster.hull_ewkt, cluster.centroid_ewkt)
            zone.population_est, zone.population_source = self._population(
                {p.admin_area_id for p in cluster.points if p.admin_area_id}, evidence)
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
            self.zones.set_shape_from_district(zone, district_id)
            zone.population_est = district.population
            zone.population_source = "gazetteer" if district.population else None
            self._persist(zone, created, taken, result)
            evidence = self.zones.evidence(reports.get(district_id, {}))
            self._record_event(self._finalize(zone, evidence, policy.boost(indicators.get(district_id)), now,
                                              created), result)

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
                  created: bool) -> ZoneEscalated | None:
        weights = {sid: self.scorer.weight(ev, now) for sid, ev, _ in evidence}
        signals = [ev for _, ev, _ in evidence]
        score = self.scorer.score(weights.values(), boost)
        ok = self.scorer.evidence_ok(signals, boost)
        status, since = self.machine.next(zone.status, score, ok, zone.below_resolve_since, now,
                                          self.zones.water_arrived(weights, now - self.WATER_WINDOW))
        zone.score, zone.status, zone.below_resolve_since = score, status, since
        zone.independent_sources = self.scorer.independent_sources(signals)
        if evidence:
            zone.last_seen = now
        self.zones.replace_signals(zone.id, weights)
        self.zones.snapshot(zone.id, now, score, len(evidence))
        current = self.zones.average_score(zone.id, now - timedelta(days=7), now)
        previous = self.zones.average_score(zone.id, now - timedelta(days=14), now - timedelta(days=7))
        zone.trend = self.scorer.trend(current if current is not None else score, previous, created)
        escalating = zone.trend in ("new", "escalating") and score >= self.scorer.config.alert_score
        if escalating and status in (ACTIVE, APPROVED):
            return ZoneEscalated(zone.id, zone.hazard, zone.name, score, zone.trend, status)
        return None

    @staticmethod
    def _record_event(event: ZoneEscalated | None, result: DetectionResult) -> None:
        if event is not None:
            result.events.append(event)

    def _population(self, area_ids: set[int], evidence: Evidence) -> tuple[int | None, str | None]:
        total = self.zones.population_of(area_ids)
        if total > 0:
            return total, "gazetteer"
        reported = max((people or 0 for _, _, people in evidence), default=0)
        return (min(reported, self.MAX_REPORTED_POP), "reported") if reported else (None, None)
