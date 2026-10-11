import uuid

from sqlalchemy import func, select

from app.models import LongTermPlan, Zone
from app.repositories.base import BaseRepository


class PlanRepository(BaseRepository[LongTermPlan]):
    model = LongTermPlan

    def zone(self, zone_id: uuid.UUID) -> Zone | None:
        return self.session.get(Zone, zone_id)

    def next_version(self, zone_id: uuid.UUID) -> int:
        return (self.session.scalar(select(func.max(LongTermPlan.version)).where(LongTermPlan.zone_id == zone_id)) or 0) + 1

    def latest(self, zone_id: uuid.UUID, statuses: tuple[str, ...]) -> LongTermPlan | None:
        return self.session.scalar(select(LongTermPlan).where(LongTermPlan.zone_id == zone_id,
                                                              LongTermPlan.status.in_(statuses))
                                   .order_by(LongTermPlan.version.desc()).limit(1))

    def with_status(self, status: str) -> list[LongTermPlan]:
        return list(self.session.scalars(select(LongTermPlan).where(LongTermPlan.status == status)
                                         .order_by(LongTermPlan.created_at.desc())))

    def for_update(self, plan_id: uuid.UUID) -> LongTermPlan | None:
        return self.session.scalar(select(LongTermPlan).where(LongTermPlan.id == plan_id)
                                   .with_for_update().execution_options(populate_existing=True))
