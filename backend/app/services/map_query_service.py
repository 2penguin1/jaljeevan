from datetime import datetime, timedelta, timezone

from cachetools import TTLCache

from app.domain.hazards import HazardPolicies, band
from app.repositories.indicator_repository import IndicatorRepository
from app.repositories.map_repository import MapRepository


def _collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


class MapQueryService:
    """Builds the public map layers as GeoJSON FeatureCollections.

    The district layer is large and changes at most once per pipeline run, so it is cached per hazard in an
    app-scoped TTL cache owned by the Container (passed in, so every request shares it).
    """

    def __init__(self, maps: MapRepository, indicators: IndicatorRepository, policies: HazardPolicies,
                 district_cache: TTLCache):
        self.maps = maps
        self.indicators = indicators
        self.policies = policies
        self.district_cache = district_cache

    def zones(self, hazard: str) -> dict:
        return _collection([{
            "type": "Feature", "id": str(z["id"]), "geometry": self.maps.geometry(z["geometry"]),
            "properties": {"name": z["name"], "hazard": z["hazard"], "zone_type": z["zone_type"],
                           "status": z["status"], "score": round(z["score"], 1), "trend": z["trend"],
                           "population_est": z["population_est"], "population_urban": z["population_urban"], "independent_sources": z["independent_sources"],
                           "centroid": [round(z["lon"], 4), round(z["lat"], 4)] if z["lon"] is not None else None},
        } for z in self.maps.zones(hazard)])

    def districts(self, hazard: str) -> dict:
        if hazard not in self.district_cache:
            self.district_cache[hazard] = self._districts(hazard)
        return self.district_cache[hazard]

    def _districts(self, hazard: str) -> dict:
        policy = self.policies.get(hazard)
        latest = self.indicators.latest_by_district(policy.indicator_source)
        features = []
        for d in self.maps.districts():
            indicator = latest.get(d["id"])
            features.append({"type": "Feature", "id": d["id"], "geometry": self.maps.geometry(d["geometry"]),
                             "properties": {"id": d["id"], "name": d["name"], "state_code": d["state_code"],
                                            "indicator_value": (indicator or {}).get(policy.indicator_field),
                                            "indicator_label": policy.indicator_label,
                                            "band": band(policy.boost(indicator))}})
        return _collection(features)

    def signals(self, hazard: str, hours: int, now: datetime | None = None) -> dict:
        since = (now or datetime.now(timezone.utc)) - timedelta(hours=hours)
        return _collection([{
            "type": "Feature", "id": str(s["id"]),
            "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
            "properties": {"id": str(s["id"]), "severity": s["severity"], "source": s["source"],
                           "title": s["title"], "published_at": s["published_at"].isoformat(),
                           "zone_id": str(s["zone_id"]) if s["zone_id"] else None},
        } for s in self.maps.signals(hazard, since)])
