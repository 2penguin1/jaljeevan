"""Interfaces (ports) that services depend on. Concrete adapters live next to this file."""
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel

from app.domain.entities import RawItem


@dataclass
class LLMResult:
    parsed: BaseModel | None
    usage: dict = field(default_factory=dict)
    refused: bool = False
    provider: str = ""  # "<provider>:<model>" that produced the answer (traceability across fallbacks)


class LLMClient(Protocol):
    """Structured-output LLM. Each adapter owns its provider AND model; callers never pass model names.

    Adapters raise ExternalServiceError for availability problems (outage, 429, access denied) so that a
    FallbackLLMClient can move to the next provider. Refusals are returned (refused=True), never raised.
    """

    def parse(self, *, system: str, user: str, schema: type[BaseModel], max_tokens: int) -> LLMResult: ...


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


@dataclass(frozen=True)
class PopulationCount:
    total: int
    urban: int


class PopulationGrid(Protocol):
    """People living inside a polygon (WKT, lon/lat). None when no grid is available."""

    def count(self, wkt: str) -> PopulationCount | None: ...


class Translator(Protocol):
    """Indic text -> English (src_lang like "mr" for Marathi)."""

    def translate(self, texts: list[str], src_lang: str = "mr") -> list[str]: ...
