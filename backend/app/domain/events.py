"""Domain events. Services raise them; the EventBus delivers them to subscribers AFTER the transaction commits."""
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class ZoneEscalated:
    zone_id: uuid.UUID
    hazard: str
    name: str
    score: float
    trend: str
    status: str


@dataclass(frozen=True)
class SignalClassified:
    signal_id: uuid.UUID
