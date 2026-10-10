"""Geocoding value objects and pure geometry helpers (no database)."""
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

Point = tuple[float, float]  # (lon, lat)

SKIP_PRECISION = frozenset({"country", "unknown", "state"})  # too broad to place on the map


@dataclass(frozen=True)
class LocationQuery:
    mention: str
    state_hint: str | None
    district_hint: str | None
    precision: str
    near: Point | None = None  # centroid of the post's other resolved places


@dataclass(frozen=True)
class Resolution:
    admin_area_id: int | None
    lon: float | None
    lat: float | None
    precision: str
    confidence: float
    ambiguous: bool = False

    @classmethod
    def ambiguous_result(cls) -> "Resolution":
        return cls(None, None, None, "state", 0.0, ambiguous=True)


@dataclass(frozen=True)
class AreaCandidate:
    id: int
    level: str
    district_name: str | None
    population: int | None
    lon: float
    lat: float


def haversine_km(a: Point, b: Point) -> float:
    lon1, lat1, lon2, lat2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(h))


def centroid(points: list[Point]) -> Point:
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))
