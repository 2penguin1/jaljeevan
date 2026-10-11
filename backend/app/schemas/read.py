import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.domain.taxonomy import HAZARDS


class FeedItem(BaseModel):
    id: uuid.UUID
    title: str
    english_summary: str | None
    quote: str | None
    place: str | None
    source: str
    domain: str | None
    credibility: float | None
    severity: int | None
    hazards: list[str]
    published_at: datetime | None
    url: str | None
    zone_id: uuid.UUID | None


class FeedPage(BaseModel):
    items: list[FeedItem]
    next_cursor: str | None  # opaque: pass it back as ?cursor= for the next page


Hazard = Literal[HAZARDS]  # one source of truth: app/domain/taxonomy.py


class ZoneSummary(BaseModel):
    id: uuid.UUID
    name: str
    hazard: Hazard
    zone_type: str
    status: str
    score: float
    trend: str
    independent_sources: int
    population_est: int | None
    population_urban: int | None  # of population_est; rural = the rest (only from the population grid)
    population_source: str | None  # worldpop (people inside the zone's shape) | gazetteer | reported
    last_seen: datetime


class ZoneInfo(ZoneSummary):
    geometry: dict | None
    centroid: list[float] | None
    district: str | None


class EvidenceItem(BaseModel):
    signal_id: uuid.UUID
    quote: str | None
    summary: str | None
    title: str
    source: str
    domain: str | None
    credibility: float | None
    weight: float
    severity: int | None
    url: str | None
    published_at: datetime | None
    place: str | None


class Contribution(BaseModel):
    signal_id: uuid.UUID
    weight: float
    share: float


class ScoreBreakdown(BaseModel):
    contributions: list[Contribution]
    indicator_boost: float
    independent_sources: int
    rule_met: bool


class TrendPoint(BaseModel):
    at: datetime
    score: float


class IndicatorInfo(BaseModel):
    label: str
    value: float | None
    band: str


class DeclarationInfo(BaseModel):
    severity: str
    declared_on: date
    order_ref: str | None
    source_url: str | None


class DroughtPanel(BaseModel):
    """The measured data behind a drought zone (GoI Drought Manual rules)."""

    label: str
    rules_version: str
    level: str  # none | watch | moderate | severe
    trigger1: bool
    t1_class: str | None
    soil_class: str | None
    spi_6p: float | None
    spi_18p: float | None
    spi_period: date | None
    soil_anomaly: float | None
    soil_period: date | None
    people_in_dry_areas: int | None
    people_in_dry_areas_urban: int | None
    imd_district_departure_pct: float | None
    imd_deficient: bool | None
    reasons: list[str]
    declared: DeclarationInfo | None


class ZoneDetail(BaseModel):
    zone: ZoneInfo
    evidence: list[EvidenceItem]
    score_breakdown: ScoreBreakdown
    trend: list[TrendPoint]
    indicators: IndicatorInfo | None
    drought: DroughtPanel | None = None


class StatsOverview(BaseModel):
    active_zones: int
    watch_zones: int
    posts_analysed_7d: int
    people_affected: int
    sources: int


class OpsRun(BaseModel):
    id: uuid.UUID
    kind: str
    started_at: datetime
    finished_at: datetime | None
    stats: dict


class TokenTotals(BaseModel):
    input_tokens: int
    output_tokens: int


class OpsTotals(BaseModel):
    signals: int
    classified: int
    rejected_by_reason: dict[str, int]
    tokens: TokenTotals
    batches_by_provider: dict[str, int]


class IndicatorFreshness(BaseModel):
    source: str
    period: date
    areas: int


class OpsSummary(BaseModel):
    runs: list[OpsRun]
    totals: OpsTotals
    indicators: list[IndicatorFreshness] = []
