"""Chain of Responsibility for place names: each resolver answers or returns None to pass to the next one.

A Resolution with ambiguous=True is an answer ("several far-apart matches") and stops the chain.
"""
import logging
import re
from typing import Protocol

from app.core.exceptions import ExternalServiceError
from app.domain.geo import SKIP_PRECISION, LocationQuery, Resolution, haversine_km
from app.domain.states import StateCodes
from app.domain.text import TextFingerprinter
from app.integrations.location import Locator
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.geocode_cache_repository import GeocodeCacheRepository

LOG = logging.getLogger(__name__)

LEVELS_FOR = {"ward": ("ward", "town", "village"), "village": ("village", "town", "ward"),
              "town": ("town", "village", "ward"), "district": ("district",)}
_SUFFIX = re.compile(r"\b(district|dist|ward|city|tehsil|taluk|taluka|village|nagar palika|block|mandal)\b")


class LocationResolver(Protocol):
    def resolve(self, query: LocationQuery) -> Resolution | None: ...


class GazetteerResolver:
    """Our own 558k-place gazetteer, constrained by state then district, with proximity tie-breaking."""

    SAME_PLACE_KM = 10

    def __init__(self, areas: AdminAreaRepository, fingerprinter: TextFingerprinter | None = None):
        self.areas = areas
        self.fp = fingerprinter or TextFingerprinter()

    def clean(self, name: str) -> str:
        return self.fp.norm_name(_SUFFIX.sub(" ", self.fp.norm_name(name)))

    def resolve(self, query: LocationQuery) -> Resolution | None:
        name = self.clean(query.mention)
        if not name:
            return None
        levels = LEVELS_FOR.get(query.precision, ("town", "village", "ward"))
        candidates = self.areas.find_candidates(name, levels, StateCodes.code(query.state_hint))
        district_matched = False
        if query.district_hint and candidates:
            wanted = self.clean(query.district_hint)
            narrowed = [c for c in candidates if self.fp.norm_name(c.district_name or "") == wanted]
            if narrowed:
                candidates, district_matched = narrowed, True
        if not candidates:
            return None
        if len(candidates) == 1:
            c = candidates[0]
            return Resolution(c.id, c.lon, c.lat, c.level, 0.95 if district_matched else 0.9)
        if query.near:
            c = min(candidates, key=lambda c: haversine_km((c.lon, c.lat), query.near))
            return Resolution(c.id, c.lon, c.lat, c.level, 0.6)
        first = candidates[0]
        if all(haversine_km((first.lon, first.lat), (c.lon, c.lat)) <= self.SAME_PLACE_KM for c in candidates[1:]):
            c = max(candidates, key=lambda c: c.population or 0)  # duplicates of one place
            return Resolution(c.id, c.lon, c.lat, c.level, 0.7)
        return Resolution.ambiguous_result()


class LocatorResolver:
    """Fallback to an external geocoder (Amazon Location), cached, and accepted only inside the hinted state."""

    def __init__(self, locator: Locator, cache: GeocodeCacheRepository, areas: AdminAreaRepository):
        self.locator = locator
        self.cache = cache
        self.areas = areas

    def resolve(self, query: LocationQuery) -> Resolution | None:
        state_code = StateCodes.code(query.state_hint)
        if not state_code:
            return None  # without a state we cannot verify the answer
        text = ", ".join(x for x in (query.mention, query.district_hint, StateCodes.name(state_code), "India") if x)
        points = self.cache.get_points(text)
        if points is None:
            try:
                points = self.locator.geocode(text)
            except ExternalServiceError as exc:
                LOG.warning("locator unavailable: %s", exc)
                return None
            self.cache.put_points(text, points)
        if not points:
            return None
        lon, lat = points[0]
        if self.areas.state_of_point(lon, lat) != state_code:
            return None
        precision = query.precision if query.precision in LEVELS_FOR else "town"
        return Resolution(None, lon, lat, precision, 0.6)


COUNTRY_NAMES = frozenset({"india", "bharat", "भारत", "hindustan"})


class ResolverChain:
    def __init__(self, resolvers: list[LocationResolver], fingerprinter: TextFingerprinter | None = None):
        self.resolvers = resolvers
        self.fp = fingerprinter or TextFingerprinter()

    def _is_broad(self, query: LocationQuery) -> bool:
        """Never trust the model's precision for country/state names: they must not become fine points."""
        return (query.precision in SKIP_PRECISION or self.fp.norm_name(query.mention) in COUNTRY_NAMES
                or StateCodes.code(query.mention) is not None)

    def resolve(self, query: LocationQuery) -> Resolution | None:
        if self._is_broad(query):
            return None
        for resolver in self.resolvers:
            result = resolver.resolve(query)
            if result is not None:
                return result
        return None
