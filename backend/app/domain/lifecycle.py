"""Zone lifecycle as an explicit state machine with hysteresis (so zones don't flicker on and off)."""
from datetime import datetime, timedelta

from app.domain.scoring import ScoringConfig

WATCH, ACTIVE, APPROVED, RESOLVING, RESOLVED, DISMISSED = (
    "watch", "active", "approved", "resolving", "resolved", "dismissed")


class ZoneStateMachine:
    """watch -> active (score >= activate with evidence) -> resolving (below resolve threshold for N hours
    AND people report water arrived) -> resolved (government confirms, outside this class).

    'approved' (government approved a brief) is never demoted by weak evidence; 'dismissed' is terminal.
    """

    def __init__(self, config: ScoringConfig):
        self.config = config

    def next(self, current: str, score: float, evidence_ok: bool, below_since: datetime | None, now: datetime,
             water_arrived: bool) -> tuple[str, datetime | None]:
        c = self.config
        if current == DISMISSED:
            return current, below_since
        if current in (RESOLVED, RESOLVING):
            if score >= c.activate and evidence_ok:
                return ACTIVE, None             # re-emerged
            return current, below_since         # sticky until it truly re-emerges (no flicker)
        if score < c.resolve_below and current in (ACTIVE, APPROVED):
            since = below_since or now
            if now - since >= timedelta(hours=c.resolve_hours) and water_arrived:
                return RESOLVING, since
            return current, since
        if current == APPROVED:
            return current, None
        if not evidence_ok:
            return WATCH, None
        if score >= c.activate:
            return ACTIVE, None
        return (current if current in (ACTIVE, WATCH) else WATCH), None
