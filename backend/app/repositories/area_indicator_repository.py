from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.models import AreaIndicator
from app.repositories.base import BaseRepository

Row = tuple[int, date, str, str, float]  # (area_id, period, source, metric, value)


class AreaIndicatorRepository(BaseRepository[AreaIndicator]):
    model = AreaIndicator
    BATCH = 5000

    def upsert_many(self, rows: list[Row]) -> int:
        """Insert or overwrite values (re-running a period replaces it). Returns rows written."""
        for i in range(0, len(rows), self.BATCH):  # 5 parameters per row; Postgres allows 65,535 per statement
            chunk = rows[i:i + self.BATCH]
            stmt = insert(AreaIndicator).values([{"area_id": a, "period": p, "source": s, "metric": m, "value": v}
                                                 for a, p, s, m, v in chunk])
            stmt = stmt.on_conflict_do_update(index_elements=["area_id", "period", "source", "metric"],
                                              set_={"value": stmt.excluded.value})
            self.session.execute(stmt)
        self.session.flush()
        return len(rows)

    def latest_period(self, source: str) -> date | None:
        return self.session.scalar(select(func.max(AreaIndicator.period)).where(AreaIndicator.source == source))

    def latest(self, source: str, area_ids: list[int] | None = None) -> dict[int, dict]:
        """{area_id: {"period": d, metric: value, ...}} for the source's most recent period."""
        period = self.latest_period(source)
        if period is None:
            return {}
        query = select(AreaIndicator).where(AreaIndicator.source == source, AreaIndicator.period == period)
        if area_ids is not None:
            query = query.where(AreaIndicator.area_id.in_(area_ids))
        out: dict[int, dict] = {}
        for row in self.session.scalars(query):
            out.setdefault(row.area_id, {"period": row.period})[row.metric] = row.value
        return out

    def freshness(self) -> list[tuple[str, date, int]]:
        """(source, latest period, areas covered in it) per source, for the ops page."""
        rows = self.session.execute(text("""
            SELECT i.source, i.period, COUNT(DISTINCT i.area_id) AS n FROM area_indicators i
            JOIN (SELECT source, MAX(period) AS period FROM area_indicators GROUP BY source) m
              ON m.source = i.source AND m.period = i.period
            GROUP BY i.source, i.period ORDER BY i.source""")).all()
        return [(r.source, r.period, r.n) for r in rows]
