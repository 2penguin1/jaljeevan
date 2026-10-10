"""Interfaces (ports) that services depend on. Concrete adapters live next to this file."""
from typing import Protocol

from app.domain.entities import RawItem


class SourceFetcher(Protocol):
    name: str
    enabled: bool

    def fetch(self) -> list[RawItem]: ...


class RawArchive(Protocol):
    def save(self, source: str, items: list[RawItem], run_id: str) -> str: ...

    def read(self, key: str) -> list[RawItem]: ...


class WeatherProvider(Protocol):
    def daily(self, points: list[tuple[int, float, float]]) -> dict[int, dict]:
        """Map district_id -> {'tmax_c', 'apparent_tmax_c', 'precip_mm_24h'} for today's forecast."""
        ...
