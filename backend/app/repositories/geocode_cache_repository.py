from app.models import GeocodeCache
from app.repositories.base import BaseRepository


class GeocodeCacheRepository(BaseRepository[GeocodeCache]):
    model = GeocodeCache

    def get_points(self, query: str) -> list[list[float]] | None:
        row = self.get(query)
        return None if row is None else row.result.get("points", [])

    def put_points(self, query: str, points: list[tuple[float, float]]) -> None:
        self.session.merge(GeocodeCache(query=query, result={"points": [list(p) for p in points]}))
        self.session.flush()
