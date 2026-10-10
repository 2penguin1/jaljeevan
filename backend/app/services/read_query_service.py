import json
import uuid
from datetime import datetime, timedelta, timezone

from app.core.exceptions import DomainValidationError, NotFoundError
from app.domain.hazards import HazardPolicies, band
from app.domain.scoring import ZoneScorer
from app.repositories.indicator_repository import IndicatorRepository
from app.repositories.pipeline_run_repository import PipelineRunRepository
from app.repositories.read_repository import ReadRepository
from app.repositories.zone_repository import ZoneRepository
from app.schemas.read import (Contribution, EvidenceItem, FeedItem, FeedPage, IndicatorInfo, OpsRun, OpsSummary,
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
                 runs: PipelineRunRepository, scorer: ZoneScorer, policies: HazardPolicies):
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
                                     band=band(boost)) if indicator else None)

    def overview(self, now: datetime | None = None) -> StatsOverview:
        since = (now or datetime.now(timezone.utc)) - timedelta(days=7)
        return StatsOverview.model_validate(self.reads.overview(since))

    def ops(self) -> OpsSummary:
        return OpsSummary(runs=[OpsRun.model_validate(r, from_attributes=True) for r in self.runs.latest(20)],
                          totals=OpsTotals.model_validate(self.reads.totals()))
