import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import Signal
from app.repositories.base import BaseRepository


class SignalRepository(BaseRepository[Signal]):
    model = Signal

    def insert_if_new(self, **values) -> uuid.UUID | None:
        """Insert unless url/content_hash already exists (safe for overlapping runs). Returns the new id or None."""
        values.setdefault("id", uuid.uuid4())
        stmt = insert(Signal).values(**values).on_conflict_do_nothing().returning(Signal.id)
        new_id = self.session.execute(stmt).scalar_one_or_none()
        self.session.flush()
        return new_id

    def recent_fingerprints(self, since: datetime) -> list[tuple[uuid.UUID, int]]:
        """(id, simhash) of recent originals that can be near-duplicated."""
        rows = self.session.execute(select(Signal.id, Signal.simhash).where(
            Signal.created_at >= since, Signal.dup_of.is_(None), Signal.status != "rejected")).all()
        return [(r.id, r.simhash) for r in rows]

    def get_many(self, ids) -> list[Signal]:
        ids = list(ids)
        return list(self.session.scalars(select(Signal).where(Signal.id.in_(ids)))) if ids else []

    def pending_ids(self, limit: int) -> list[uuid.UUID]:
        return list(self.session.scalars(select(Signal.id).where(Signal.status == "pending").limit(limit)))
