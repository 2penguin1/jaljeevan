import uuid

from sqlalchemy import func, select

from app.models import Campaign, Organization, Pledge, VolunteerSignup, VolunteerTask, Zone
from app.repositories.base import BaseRepository


class CommunityRepository(BaseRepository[Campaign]):
    """NGO campaigns with pledges, and volunteer tasks with sign-ups."""

    model = Campaign

    def zone(self, zone_id: uuid.UUID | None) -> Zone | None:
        return self.session.get(Zone, zone_id) if zone_id else None

    def org(self, org_id: uuid.UUID) -> Organization | None:
        return self.session.get(Organization, org_id)

    def campaigns(self, zone_id: uuid.UUID | None) -> list[tuple[Campaign, float, int]]:
        totals = (select(Pledge.campaign_id, func.coalesce(func.sum(Pledge.amount_inr), 0).label("total"),
                         func.count(Pledge.id).label("n")).group_by(Pledge.campaign_id).subquery())
        query = (select(Campaign, func.coalesce(totals.c.total, 0), func.coalesce(totals.c.n, 0))
                 .outerjoin(totals, totals.c.campaign_id == Campaign.id).where(Campaign.status == "active")
                 .order_by(Campaign.created_at.desc()))
        if zone_id:
            query = query.where(Campaign.zone_id == zone_id)
        return [(c, float(t), int(n)) for c, t, n in self.session.execute(query).all()]

    def tasks(self, zone_id: uuid.UUID | None) -> list[tuple[VolunteerTask, int]]:
        taken = select(VolunteerSignup.task_id, func.count().label("n")).group_by(VolunteerSignup.task_id).subquery()
        query = (select(VolunteerTask, func.coalesce(taken.c.n, 0)).outerjoin(taken, taken.c.task_id == VolunteerTask.id)
                 .order_by(VolunteerTask.task_date.nulls_last(), VolunteerTask.created_at.desc()))
        if zone_id:
            query = query.where(VolunteerTask.zone_id == zone_id)
        return [(t, int(n)) for t, n in self.session.execute(query).all()]

    def task_for_update(self, task_id: uuid.UUID) -> VolunteerTask | None:
        return self.session.scalar(select(VolunteerTask).where(VolunteerTask.id == task_id)
                                   .with_for_update().execution_options(populate_existing=True))

    def signups(self, task_id: uuid.UUID) -> int:
        return self.session.scalar(select(func.count()).select_from(VolunteerSignup)
                                   .where(VolunteerSignup.task_id == task_id)) or 0

    def signed_up_tasks(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        return set(self.session.scalars(select(VolunteerSignup.task_id).where(VolunteerSignup.user_id == user_id)))
