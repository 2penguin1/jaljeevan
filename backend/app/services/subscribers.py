"""EventBus subscribers available in P1. SNS alert emails are added in P2 (AWS)."""
import json
import logging
from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.events import SignalClassified, ZoneEscalated

LOG = logging.getLogger(__name__)


class AlertLogSubscriber:
    def __call__(self, event: ZoneEscalated) -> None:
        LOG.warning("ALERT %s zone %s (%s): score %.1f, %s", event.hazard, event.name, event.zone_id,
                    event.score, event.trend)


class LiveFeedNotifier:
    """Postgres NOTIFY on 'signal_classified' / 'zone_escalated'; the API's SSE endpoint LISTENs (P3)."""

    def __init__(self, session_scope: Callable[[], AbstractContextManager[Session]]):
        self.session_scope = session_scope

    def __call__(self, event) -> None:
        if isinstance(event, SignalClassified):
            channel, payload = "signal_classified", str(event.signal_id)
        elif isinstance(event, ZoneEscalated):
            channel, payload = "zone_escalated", json.dumps({"zone_id": str(event.zone_id), "score": event.score,
                                                             "hazard": event.hazard, "name": event.name})
        else:
            return
        with self.session_scope() as session:
            session.execute(text("SELECT pg_notify(:c, :p)"), {"c": channel, "p": payload})
