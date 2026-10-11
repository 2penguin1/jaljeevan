"""Which tanker vendors to invite to a tender, and why: in reach by road, has tankers, ranked on four plain factors."""
import math
import statistics
from dataclasses import dataclass

ROAD_FACTOR = 1.3      # straight-line distance x 1.3 approximates road distance
INVITE = 6
DEFAULT_PRICE = 60.0   # Rs per kL when no vendor is in reach to compare with
WEIGHTS = {"distance": 0.35, "price": 0.25, "capacity": 0.20, "reliability": 0.20}


@dataclass(frozen=True)
class Vendor:
    key: object
    lat: float
    lon: float
    tanker_count: int
    capacity_kl: float
    price: float
    reliability: float


@dataclass(frozen=True)
class VendorMatch:
    vendor: Vendor
    road_km: float
    score: float
    reason: str


def road_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h)) * ROAD_FACTOR


def match_vendors(zone: tuple[float, float], vendors: list[Vendor], radius_km: float,
                  need_kl_per_day: float) -> list[VendorMatch]:
    reach = [(v, road_km(zone, (v.lat, v.lon))) for v in vendors if v.tanker_count > 0]
    reach = [(v, d) for v, d in reach if d <= radius_km]
    if not reach:
        return []
    cheapest = min(v.price for v, _ in reach)
    out = []
    for v, d in reach:
        per_day = v.tanker_count * v.capacity_kl  # one trip per tanker a day
        score = (WEIGHTS["distance"] * (1 - d / radius_km) + WEIGHTS["price"] * cheapest / v.price
                 + WEIGHTS["capacity"] * min(1.0, per_day / max(need_kl_per_day, 1))
                 + WEIGHTS["reliability"] * v.reliability)
        reason = (f"{d:.0f} km by road, ₹{v.price:g}/kL, {v.tanker_count} tankers ({per_day:g} kL a day), "
                  f"{v.reliability:.0%} of past orders delivered")
        out.append(VendorMatch(v, round(d, 1), round(score, 3), reason))
    return sorted(out, key=lambda m: m.score, reverse=True)[:INVITE]


def suggested_price(matches: list[VendorMatch]) -> float:
    return float(statistics.median(m.vendor.price for m in matches)) if matches else DEFAULT_PRICE
