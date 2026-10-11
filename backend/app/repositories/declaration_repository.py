from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import DroughtDeclaration
from app.repositories.base import BaseRepository


class DeclarationRepository(BaseRepository[DroughtDeclaration]):
    model = DroughtDeclaration

    def upsert(self, area_id: int, state_code: str, declared_on: date, severity: str, order_ref: str | None,
               source_url: str | None) -> None:
        values = {"area_id": area_id, "state_code": state_code, "declared_on": declared_on, "severity": severity,
                  "order_ref": order_ref, "source_url": source_url}
        stmt = insert(DroughtDeclaration).values(**values).on_conflict_do_update(
            index_elements=["area_id", "declared_on"],
            set_={k: values[k] for k in ("severity", "order_ref", "source_url")})
        self.session.execute(stmt)
        self.session.flush()

    def active(self, since: date) -> dict[int, DroughtDeclaration]:
        """Latest declaration per area declared on or after `since` (a declaration lasts up to 6 months)."""
        out: dict[int, DroughtDeclaration] = {}
        query = select(DroughtDeclaration).where(DroughtDeclaration.declared_on >= since) \
            .order_by(DroughtDeclaration.declared_on)
        for row in self.session.scalars(query):
            out[row.area_id] = row
        return out
