import uuid

from sqlalchemy import func, select

from app.models import ReliefBrief
from app.repositories.base import BaseRepository


class BriefRepository(BaseRepository[ReliefBrief]):
    model = ReliefBrief

    def next_version(self, zone_id: uuid.UUID) -> int:
        return (self.session.scalar(select(func.max(ReliefBrief.version)).where(ReliefBrief.zone_id == zone_id)) or 0) + 1

    def latest(self, zone_id: uuid.UUID, statuses: tuple[str, ...]) -> ReliefBrief | None:
        return self.session.scalar(select(ReliefBrief).where(ReliefBrief.zone_id == zone_id, ReliefBrief.status.in_(statuses))
                                   .order_by(ReliefBrief.version.desc()).limit(1))

    def with_status(self, status: str) -> list[ReliefBrief]:
        return list(self.session.scalars(select(ReliefBrief).where(ReliefBrief.status == status)
                                         .order_by(ReliefBrief.created_at.desc())))

    def for_update(self, brief_id: uuid.UUID) -> ReliefBrief | None:
        return self.session.scalar(select(ReliefBrief).where(ReliefBrief.id == brief_id)
                                   .with_for_update().execution_options(populate_existing=True))
