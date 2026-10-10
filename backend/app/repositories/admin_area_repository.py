from geoalchemy2.elements import WKTElement
from sqlalchemy import insert, select, text

from app.models import AdminArea
from app.repositories.base import BaseRepository


class AdminAreaRepository(BaseRepository[AdminArea]):
    model = AdminArea
    _BATCH = 5000

    def bulk_insert(self, rows: list[dict]) -> int:
        """Rows carry a 'wkt' key (geometry as WKT, SRID 4326) instead of 'geom'."""
        prepared = [{**{k: v for k, v in r.items() if k != "wkt"},
                     "geom": WKTElement(r["wkt"], srid=4326)} for r in rows]
        for i in range(0, len(prepared), self._BATCH):
            self.session.execute(insert(AdminArea), prepared[i:i + self._BATCH])
        self.session.flush()
        return len(prepared)

    def has_any(self) -> bool:
        return self.session.scalar(select(AdminArea.id).limit(1)) is not None

    def find_district_id(self, state_code: str, name_norm: str) -> int | None:
        return self.session.scalar(select(AdminArea.id).where(
            AdminArea.level == "district", AdminArea.state_code == state_code, AdminArea.name_norm == name_norm))

    def link_parents(self) -> None:
        """Attach towns/villages/wards to the district polygon containing them; fill missing district population."""
        self.session.execute(text("""
            UPDATE admin_areas a SET parent_id = d.id, district_name = d.name
            FROM admin_areas d
            WHERE d.level = 'district' AND a.level IN ('town','village','ward')
              AND a.parent_id IS NULL AND ST_Intersects(d.geom, ST_PointOnSurface(a.geom))"""))
        self.session.execute(text("""
            UPDATE admin_areas d SET population = s.total
            FROM (SELECT parent_id, SUM(population) AS total FROM admin_areas
                  WHERE level IN ('town','village') GROUP BY parent_id) s
            WHERE d.id = s.parent_id AND d.level = 'district' AND d.population IS NULL"""))
        self.session.flush()
