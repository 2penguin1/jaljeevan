import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update

from app.models import Notification, User
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    """Private, per-user notifications. Every query is scoped to one user."""

    model = Notification

    def org_user_ids(self, org_id: uuid.UUID | None) -> list[uuid.UUID]:
        if org_id is None:
            return []
        return list(self.session.scalars(select(User.id).where(User.org_id == org_id)))

    def latest(self, user_id: uuid.UUID, limit: int = 30) -> list[Notification]:
        return list(self.session.scalars(select(Notification).where(Notification.user_id == user_id)
                                         .order_by(Notification.created_at.desc()).limit(limit)))

    def unread_count(self, user_id: uuid.UUID) -> int:
        return self.session.scalar(select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id, Notification.read_at.is_(None))) or 0

    def mark_read(self, user_id: uuid.UUID, ids: list[uuid.UUID] | None) -> None:
        query = update(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))
        if ids:
            query = query.where(Notification.id.in_(ids))  # someone else's ids simply match nothing
        self.session.execute(query.values(read_at=datetime.now(timezone.utc)))
        self.session.flush()
