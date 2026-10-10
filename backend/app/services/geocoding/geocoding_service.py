from app.domain.geo import LocationQuery, Resolution, centroid
from app.models import Signal
from app.repositories.signal_repository import SignalRepository
from app.services.geocoding.resolvers import ResolverChain


class GeocodingService:
    """Places a signal's location mentions on the map in two passes.

    Pass 1 resolves unambiguous names. Pass 2 retries ambiguous ones using the centroid of pass-1 places
    ("Rampur" next to "Barmer" -> the Rampur near Barmer). Still-ambiguous names are stored without
    geometry and never feed fine-grained zone clustering.
    """

    def __init__(self, chain: ResolverChain, signals: SignalRepository):
        self.chain = chain
        self.signals = signals

    def geocode(self, signal: Signal) -> int:
        mentions = (signal.meta or {}).get("locations") or []
        resolved: list[tuple[dict, Resolution]] = []
        ambiguous: list[dict] = []
        for m in mentions:
            result = self.chain.resolve(self._query(m))
            if result is None:
                continue
            if result.ambiguous:
                ambiguous.append(m)
            else:
                resolved.append((m, result))
        if ambiguous and resolved:
            near = centroid([(r.lon, r.lat) for _, r in resolved])
            still = []
            for m in ambiguous:
                result = self.chain.resolve(self._query(m, near))
                if result is not None and not result.ambiguous:
                    resolved.append((m, result))
                else:
                    still.append(m)
            ambiguous = still
        rows = [self._row(m["mention"], r) for m, r in resolved]
        rows += [{"mention_text": m["mention"][:300], "admin_area_id": None, "precision": "state",
                  "geo_confidence": 0.0, "ambiguous": True, "lon": None, "lat": None} for m in ambiguous]
        self.signals.replace_locations(signal.id, rows)
        return len(rows)

    @staticmethod
    def _query(m: dict, near=None) -> LocationQuery:
        return LocationQuery(m["mention"], m.get("state_hint"), m.get("district_hint"), m["precision"], near)

    @staticmethod
    def _row(mention: str, r: Resolution) -> dict:
        return {"mention_text": mention[:300], "admin_area_id": r.admin_area_id, "precision": r.precision,
                "geo_confidence": r.confidence, "ambiguous": False, "lon": r.lon, "lat": r.lat}
