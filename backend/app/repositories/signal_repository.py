import uuid
from datetime import datetime

from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.models import Signal, SignalFeedback, SignalLabel, SignalLocation
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

    def recent_fingerprints(self, since: datetime) -> list[tuple[uuid.UUID, int, str]]:
        """(id, simhash, title) of recent originals that can be near-duplicated."""
        rows = self.session.execute(select(Signal.id, Signal.simhash, Signal.title).where(
            Signal.created_at >= since, Signal.dup_of.is_(None), Signal.status != "rejected")).all()
        return [(r.id, r.simhash, r.title or "") for r in rows]

    def get_many(self, ids) -> list[Signal]:
        ids = list(ids)
        return list(self.session.scalars(select(Signal).where(Signal.id.in_(ids)))) if ids else []

    def replace_labels(self, signal_id: uuid.UUID, labels: list[dict]) -> None:
        """Idempotent: re-classification replaces the previous labels instead of adding to them."""
        self.session.execute(delete(SignalLabel).where(SignalLabel.signal_id == signal_id))
        self.session.add_all([SignalLabel(signal_id=signal_id, **label) for label in labels])
        self.session.flush()

    def replace_locations(self, signal_id: uuid.UUID, rows: list[dict]) -> None:
        """Idempotent: rows carry lon/lat (None for ambiguous mentions) instead of a geometry."""
        self.session.execute(delete(SignalLocation).where(SignalLocation.signal_id == signal_id))
        for r in rows:
            geom = WKTElement(f"POINT({r['lon']} {r['lat']})", srid=4326) if r["lon"] is not None else None
            self.session.add(SignalLocation(signal_id=signal_id, geom=geom,
                                            **{k: v for k, v in r.items() if k not in ("lon", "lat")}))
        self.session.flush()

    def relevant_classified(self, ids) -> list[Signal]:
        ids = list(ids)
        if not ids:
            return []
        return list(self.session.scalars(select(Signal).where(
            Signal.id.in_(ids), Signal.status == "classified", Signal.relevant.is_(True))))

    def recent_contrasts(self, limit: int = 10) -> list[str]:
        """Summaries of posts reviewers marked false/irrelevant: fed back to the classifier as counter-examples."""
        rows = self.session.scalars(
            select(Signal.english_summary)  # model-written summary only, never the raw post title
            .join(SignalFeedback, SignalFeedback.signal_id == Signal.id)
            .where(SignalFeedback.verdict.in_(("false", "irrelevant")))
            .order_by(SignalFeedback.created_at.desc()).limit(limit))
        return [r[:160] for r in rows if r]

    def pending_ids(self, limit: int) -> list[uuid.UUID]:
        return list(self.session.scalars(select(Signal.id).where(Signal.status == "pending").limit(limit)))
