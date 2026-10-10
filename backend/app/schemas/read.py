import uuid
from datetime import datetime

from pydantic import BaseModel


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
    next_cursor: datetime | None


class ZoneSummary(BaseModel):
    id: uuid.UUID
    name: str
    hazard: str
    zone_type: str
    status: str
    score: float
    trend: str
    independent_sources: int
    population_est: int | None
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


class ZoneDetail(BaseModel):
    zone: ZoneInfo
    evidence: list[EvidenceItem]
    score_breakdown: ScoreBreakdown
    trend: list[TrendPoint]
    indicators: IndicatorInfo | None


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


class OpsSummary(BaseModel):
    runs: list[OpsRun]
    totals: OpsTotals
