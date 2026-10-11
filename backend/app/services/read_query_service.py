import json
import uuid
from datetime import datetime, timedelta, timezone

from app.core.exceptions import DomainValidationError, NotFoundError
from app.domain.drought import FOOTPRINT_LABEL, RULES_VERSION
from app.repositories.area_indicator_repository import AreaIndicatorRepository
from app.services.drought_assessor import AreaDrought, DroughtAssessor
from app.domain.hazards import HazardPolicies, band
from app.domain.scoring import ZoneScorer
from app.repositories.indicator_repository import IndicatorRepository
from app.repositories.pipeline_run_repository import PipelineRunRepository
from app.repositories.read_repository import ReadRepository
from app.repositories.zone_repository import ZoneRepository
from app.schemas.read import (Contribution, DeclarationInfo, DroughtPanel, IndicatorFreshness, EvidenceItem, FeedItem, FeedPage, IndicatorInfo, OpsRun, OpsSummary,
                              OpsTotals, ScoreBreakdown, StatsOverview, TrendPoint, ZoneDetail, ZoneInfo,
                              ZoneSummary)


def encode_cursor(sort_at: datetime, signal_id: uuid.UUID) -> str:
    return f"{sort_at.isoformat()}|{signal_id}"


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Opaque feed cursor "<timestamp>|<id>"; anything else is a 422, not a 500."""
    try:
        at, signal_id = cursor.split("|")
        return datetime.fromisoformat(at), uuid.UUID(signal_id)
    except ValueError:
        raise DomainValidationError("cursor is not valid; use next_cursor from the previous page") from None


class ReadQueryService:
    """Assembles the public read models. Numbers (shares, rule checks) come from code, never from text."""

    def __init__(self, reads: ReadRepository, zones: ZoneRepository, indicators: IndicatorRepository,
                 runs: PipelineRunRepository, scorer: ZoneScorer, policies: HazardPolicies,
                 drought: DroughtAssessor | None = None, area_indicators: AreaIndicatorRepository | None = None):
        self.drought = drought
        self.area_indicators = area_indicators
        self.reads = reads
        self.zones = zones
        self.indicators = indicators
        self.runs = runs
        self.scorer = scorer
        self.policies = policies

    def feed(self, cursor: str | None, limit: int) -> FeedPage:
        rows = self.reads.feed(decode_cursor(cursor) if cursor else None, limit)
        last = rows[-1] if len(rows) == limit else None
        next_cursor = encode_cursor(last["sort_at"], last["id"]) if last else None
        return FeedPage(items=[FeedItem.model_validate(r) for r in rows], next_cursor=next_cursor)

    def zones_list(self, hazard: str | None, status: str | None) -> list[ZoneSummary]:
        return [ZoneSummary.model_validate(r) for r in self.reads.zones(hazard, status)]

    def zone_detail(self, zone_id: uuid.UUID) -> ZoneDetail:
        row = self.reads.zone(zone_id)
        if row is None:
            raise NotFoundError(f"zone {zone_id} not found")
        evidence = self.reads.zone_evidence(zone_id)
        policy = self.policies.get(row["hazard"])
        drought = None
        if policy.zoning == "footprint" and row.get("area_id") and self.drought is not None:
            drought = self.drought.assess(datetime.now(timezone.utc), [row["area_id"]]).get(row["area_id"])
            indicator = None  # the drought panel replaces the district indicator
            boost = drought.assessment.boost if drought else 0.0
        else:
            indicator = (self.indicators.latest_by_district(policy.indicator_source).get(row["district_id"])
                         if row["district_id"] else None)
            boost = policy.boost(indicator)
        scoring_evidence = [ev for _, ev, _ in self.zones.evidence({e["signal_id"]: 1.0 for e in evidence})]
        total = sum(e["weight"] for e in evidence)
        zone = ZoneInfo.model_validate({**row, "geometry": json.loads(row["geometry"]) if row["geometry"] else None,
                                        "centroid": [row["lon"], row["lat"]] if row["lon"] is not None else None})
        return ZoneDetail(
            zone=zone,
            evidence=[EvidenceItem.model_validate(e) for e in evidence],
            score_breakdown=ScoreBreakdown(
                contributions=[Contribution(signal_id=e["signal_id"], weight=e["weight"],
                                            share=e["weight"] / total if total else 0.0) for e in evidence],
                indicator_boost=boost,
                independent_sources=self.scorer.independent_sources(scoring_evidence),
                rule_met=self.scorer.evidence_ok(scoring_evidence, boost)),
            trend=[TrendPoint.model_validate(t) for t in self.reads.zone_trend(zone_id)],
            indicators=IndicatorInfo(label=policy.indicator_label, value=indicator.get(policy.indicator_field),
                                     band=band(boost)) if indicator else None,
            drought=self._drought_panel(drought) if drought else None)

    @staticmethod
    def _drought_panel(d: AreaDrought) -> DroughtPanel:
        a, m = d.assessment, d.metrics
        decl = m.get("declaration")
        as_int = lambda v: int(v) if v is not None else None  # noqa: E731
        return DroughtPanel(
            label=FOOTPRINT_LABEL, rules_version=RULES_VERSION, level=a.level, trigger1=a.trigger1,
            t1_class=a.t1_class, soil_class=a.soil_class, spi_6p=m.get("spi_6p"), spi_18p=m.get("spi_18p"),
            spi_period=m.get("spi_period"), soil_anomaly=m.get("soil_anomaly"), soil_period=m.get("soil_period"),
            people_in_dry_areas=as_int(m.get("pop_stressed")), people_in_dry_areas_urban=as_int(m.get("pop_stressed_urban")),
            imd_district_departure_pct=m.get("imd_departure_pct"), imd_deficient=a.imd_deficient,
            reasons=list(a.reasons),
            declared=DeclarationInfo(severity=decl.severity, declared_on=decl.declared_on, order_ref=decl.order_ref,
                                     source_url=decl.source_url) if decl else None)

    def overview(self, now: datetime | None = None) -> StatsOverview:
        since = (now or datetime.now(timezone.utc)) - timedelta(days=7)
        return StatsOverview.model_validate(self.reads.overview(since))

    def ops(self) -> OpsSummary:
        freshness = self.area_indicators.freshness() if self.area_indicators is not None else []
        return OpsSummary(runs=[OpsRun.model_validate(r, from_attributes=True) for r in self.runs.latest(20)],
                          totals=OpsTotals.model_validate(self.reads.totals()),
                          indicators=[IndicatorFreshness(source=s, period=p, areas=n) for s, p, n in freshness])
