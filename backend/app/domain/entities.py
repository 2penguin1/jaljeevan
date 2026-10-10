"""Immutable value objects passed between layers. Pure Python: no ORM, no I/O."""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class RawItem:
    """One post as collected from a source, before it becomes a stored Signal."""

    source: str                 # gdelt | rss | reddit | x | citizen
    url: str | None
    title: str
    text: str
    published_at: datetime | None
    author: str | None = None
    domain: str | None = None
    lang: str | None = None
    country: str | None = None  # ISO-2 country of the outlet, when known
    meta: dict = field(default_factory=dict)
