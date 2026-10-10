"""Zone scoring rules: evidence weights, noisy-OR combination, the corroboration rule, and trend."""
from dataclasses import dataclass, field
from datetime import datetime
from math import prod

SOCIAL_SOURCES = frozenset({"reddit", "x", "citizen"})


@dataclass(frozen=True)
class ScoringConfig:
    """Every tunable number in one place (spec values)."""

    severity_factor: dict = field(default_factory=lambda: {1: 0.2, 2: 0.4, 3: 0.65, 4: 0.85, 5: 1.0})
    half_life_social_days: float = 7.0
    half_life_news_days: float = 14.0
    unknown_age_days: float = 14.0
    corroboration_bonus: float = 0.2
    activate: float = 60.0
    resolve_below: float = 35.0
    resolve_hours: float = 72.0
    escalation_delta: float = 10.0
    alert_score: float = 70.0
    official_credibility: float = 1.0


@dataclass(frozen=True)
class EvidenceSignal:
    """What scoring needs to know about one signal inside a zone (decoupled from the ORM)."""

    source: str
    domain: str | None
    author: str | None
    credibility: float
    severity: int
    published_at: datetime | None
    geo_confidence: float
    corroborated: bool = False


class ZoneScorer:
    def __init__(self, config: ScoringConfig):
        self.config = config

    def recency(self, published_at: datetime | None, now: datetime, source: str) -> float:
        half = self.config.half_life_social_days if source in SOCIAL_SOURCES else self.config.half_life_news_days
        if published_at is None:
            return 0.5 ** (self.config.unknown_age_days / half)
        age_days = max(0.0, (now - published_at).total_seconds() / 86400)
        return 0.5 ** (age_days / half)

    def weight(self, ev: EvidenceSignal, now: datetime) -> float:
        bonus = self.config.corroboration_bonus if ev.corroborated and ev.source == "citizen" else 0.0
        credibility = min(1.0, ev.credibility + bonus)
        severity = self.config.severity_factor.get(ev.severity, self.config.severity_factor[1])
        return credibility * severity * self.recency(ev.published_at, now, ev.source) * ev.geo_confidence

    @staticmethod
    def noisy_or(weights) -> float:
        clipped = [min(1.0, max(0.0, w)) for w in weights]
        return 1.0 - prod(1.0 - w for w in clipped) if clipped else 0.0

    def score(self, weights, boost: float = 0.0) -> float:
        """0-100. Independent evidence and indicator support combine like independent probabilities."""
        combined = 1.0 - (1.0 - self.noisy_or(weights)) * (1.0 - boost)
        return round(min(100.0, 100.0 * combined), 1)

    @staticmethod
    def independent_sources(evidence: list[EvidenceSignal]) -> int:
        keys = set()
        for ev in evidence:
            if ev.source in SOCIAL_SOURCES:
                keys.add((ev.source, ev.author or ev.domain))
            else:
                keys.add(("news", (ev.domain or "").removeprefix("www.")))
        return len(keys)

    def evidence_ok(self, evidence: list[EvidenceSignal], boost: float) -> bool:
        """Corroboration rule: >=2 independent sources, OR one official source, OR indicator support."""
        max_credibility = max((ev.credibility for ev in evidence), default=0.0)
        return (self.independent_sources(evidence) >= 2 or max_credibility >= self.config.official_credibility
                or boost > 0.0)

    def trend(self, current_avg: float, previous_avg: float | None, is_new: bool) -> str:
        if is_new:
            return "new"
        if previous_avg is None:
            return "stable"
        delta = current_avg - previous_avg
        if delta >= self.config.escalation_delta:
            return "escalating"
        if delta <= -self.config.escalation_delta:
            return "easing"
        return "stable"
