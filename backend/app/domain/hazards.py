"""Strategy per hazard: which indicator source it reads and how strongly indicators support a zone."""
from typing import Protocol


class HazardPolicy(Protocol):
    hazard: str
    indicator_source: str

    def boost(self, indicator: dict | None) -> float: ...


class DroughtPolicy:
    hazard = "drought"
    indicator_source = "imd"
    SEVERE_DEPARTURE = -40.0   # % below normal monsoon rainfall
    MODERATE_DEPARTURE = -20.0

    def boost(self, indicator: dict | None) -> float:
        dep = (indicator or {}).get("rainfall_departure_pct")
        if dep is None:
            return 0.0
        return 0.4 if dep <= self.SEVERE_DEPARTURE else 0.2 if dep <= self.MODERATE_DEPARTURE else 0.0


class FloodPolicy:
    hazard = "flood"
    indicator_source = "open-meteo"
    VERY_HEAVY_MM = 115.6      # IMD "very heavy rain"
    HEAVY_MM = 64.5            # IMD "heavy rain"

    def boost(self, indicator: dict | None) -> float:
        rain = (indicator or {}).get("precip_mm_24h")
        if rain is None:
            return 0.0
        return 0.4 if rain >= self.VERY_HEAVY_MM else 0.2 if rain >= self.HEAVY_MM else 0.0


class HeatPolicy:
    hazard = "heat"
    indicator_source = "open-meteo"
    SEVERE_FEELS_LIKE_C = 45.0
    HOT_MAX_C = 40.0

    def boost(self, indicator: dict | None) -> float:
        ind = indicator or {}
        if ind.get("apparent_tmax_c") is not None and ind["apparent_tmax_c"] >= self.SEVERE_FEELS_LIKE_C:
            return 0.4
        return 0.2 if ind.get("tmax_c") is not None and ind["tmax_c"] >= self.HOT_MAX_C else 0.0


class HazardPolicies:
    """Registry of hazard strategies. Adding a hazard = one new policy class registered here."""

    def __init__(self, policies: list[HazardPolicy]):
        self._by_hazard = {p.hazard: p for p in policies}

    @classmethod
    def default(cls) -> "HazardPolicies":
        return cls([DroughtPolicy(), FloodPolicy(), HeatPolicy()])

    def get(self, hazard: str) -> HazardPolicy:
        return self._by_hazard[hazard]

    def all(self) -> list[HazardPolicy]:
        return list(self._by_hazard.values())
