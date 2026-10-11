from datetime import date

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from app.models import DistrictIndicator
from app.repositories.base import BaseRepository

_VALUE_FIELDS = ("rainfall_departure_pct", "drought_index", "tmax_c", "apparent_tmax_c", "precip_mm_24h")


class IndicatorRepository(BaseRepository[DistrictIndicator]):
    model = DistrictIndicator

    def upsert(self, district_id: int, period: date, source: str, **values) -> None:
        """Insert or update one district/day/source row (idempotent re-runs)."""
        row = {"district_id": district_id, "period": period, "source": source,
               **{k: values[k] for k in _VALUE_FIELDS if k in values}}
        stmt = insert(DistrictIndicator).values(**row).on_conflict_do_update(
            index_elements=["district_id", "period", "source"],
            set_={k: row[k] for k in _VALUE_FIELDS if k in row})
        self.session.execute(stmt)
        self.session.flush()

    def district_points(self) -> list[tuple[int, float, float]]:
        """(district_id, lat, lon) of a point inside each district - used to query weather."""
        rows = self.session.execute(text(
            "SELECT id, ST_Y(ST_PointOnSurface(geom)) AS lat, ST_X(ST_PointOnSurface(geom)) AS lon "
            "FROM admin_areas WHERE level = 'district'")).all()
        return [(r.id, r.lat, r.lon) for r in rows]

    def has_period(self, source: str, period: date) -> bool:
        return self.session.scalar(text(
            "SELECT 1 FROM district_indicators WHERE source = :s AND period = :p LIMIT 1"), {"s": source, "p": period}) is not None

    def latest_by_district(self, source: str | None) -> dict[int, dict]:
        if source is None:  # hazards without a district indicator (e.g. water supply)
            return {}
        rows = self.session.execute(text(
            "SELECT DISTINCT ON (district_id) district_id, rainfall_departure_pct, tmax_c, apparent_tmax_c, "
            "precip_mm_24h FROM district_indicators WHERE source = :src ORDER BY district_id, period DESC"),
            {"src": source}).mappings()
        return {r["district_id"]: dict(r) for r in rows}
