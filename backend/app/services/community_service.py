"""NGO side: fundraising campaigns (pledges only: no money is taken) and volunteer tasks with limited slots."""
import uuid
from datetime import date

from app.core.exceptions import ConflictError, DomainValidationError, ForbiddenError, NotFoundError
from app.models import Campaign, Pledge, User, VolunteerSignup, VolunteerTask
from app.repositories.community_repository import CommunityRepository
from app.repositories.notification_repository import NotificationRepository
from app.services.notification_service import NotificationService

MAX_GOAL = 1_000_000_000
MAX_PLEDGE = 10_000_000
MAX_SLOTS = 1000


class CommunityService:
    def __init__(self, repo: CommunityRepository, notifications: NotificationService | None = None):
        self.repo = repo
        self.notifications = notifications or NotificationService(NotificationRepository(repo.session))

    # -- reads ----------------------------------------------------------------------------------------------------
    def campaigns(self, zone_id: uuid.UUID | None = None) -> list[dict]:
        out = []
        for c, total, n in self.repo.campaigns(zone_id):
            zone, org = self.repo.zone(c.zone_id), self.repo.org(c.ngo_org_id)
            out.append({"id": c.id, "title": c.title, "story": c.story, "goal_inr": c.goal_inr, "pledged_inr": total,
                        "pledges": n, "zone_id": c.zone_id, "zone_name": zone.name if zone else None,
                        "ngo_name": org.name if org else "?", "created_at": c.created_at})
        return out

    def tasks(self, zone_id: uuid.UUID | None = None, viewer: User | None = None) -> list[dict]:
        mine = self.repo.signed_up_tasks(viewer.id) if viewer else set()
        out = []
        for t, taken in self.repo.tasks(zone_id):
            zone, org = self.repo.zone(t.zone_id), self.repo.org(t.org_id)
            out.append({"id": t.id, "title": t.title, "description": t.description, "task_date": t.task_date,
                        "slots": t.slots, "taken": taken, "signed_up": t.id in mine, "zone_id": t.zone_id,
                        "zone_name": zone.name if zone else None, "ngo_name": org.name if org else "?"})
        return out

    # -- writes ---------------------------------------------------------------------------------------------------
    def start_campaign(self, actor: User, zone_id: uuid.UUID | None, title: str, story: str,
                       goal_inr: float) -> uuid.UUID:
        org_id = self._ngo(actor)
        self._zone_ok(zone_id)
        if not (0 < goal_inr <= MAX_GOAL) or not title.strip():
            raise DomainValidationError("a campaign needs a title and a goal between ₹1 and ₹100 crore")
        return self.repo.add(Campaign(ngo_org_id=org_id, zone_id=zone_id, title=title.strip()[:300],
                                      story=(story or "").strip()[:4000], goal_inr=goal_inr)).id

    def pledge(self, actor: User, campaign_id: uuid.UUID, amount_inr: float, message: str | None) -> None:
        campaign = self.repo.get(campaign_id)
        if campaign is None or campaign.status != "active":
            raise NotFoundError("campaign not found")
        if not (0 < amount_inr <= MAX_PLEDGE):
            raise DomainValidationError("a pledge must be between ₹1 and ₹1 crore")
        note = (message or "").strip()[:500] or None
        existing = self.repo.pledge_of(campaign.id, actor.id)
        if existing is not None:  # one pledge per person: pledging again changes it (no inflated totals or counts)
            existing.amount_inr, existing.message = amount_inr, note
            verb = "changed their pledge to"
        else:
            self.repo.session.add(Pledge(campaign_id=campaign.id, user_id=actor.id, amount_inr=amount_inr, message=note))
            verb = "pledged"
        self.repo.session.flush()
        self.notifications.tell_org(campaign.ngo_org_id, "pledge",
                                    f"{actor.name} {verb} ₹{amount_inr:,.0f} for “{campaign.title}”",
                                    campaign.id, actor.id, link="/community")

    def post_task(self, actor: User, zone_id: uuid.UUID | None, title: str, description: str,
                  task_date: date | None, slots: int) -> uuid.UUID:
        org_id = self._ngo(actor)
        self._zone_ok(zone_id)
        if not (0 < slots <= MAX_SLOTS) or not title.strip():
            raise DomainValidationError("a task needs a title and between 1 and 1000 slots")
        return self.repo.add(VolunteerTask(org_id=org_id, zone_id=zone_id, title=title.strip()[:300],
                                           description=(description or "").strip()[:2000], task_date=task_date,
                                           slots=slots)).id

    def sign_up(self, actor: User, task_id: uuid.UUID) -> None:
        task = self.repo.task_for_update(task_id)  # locked: two people never take the last slot together
        if task is None:
            raise NotFoundError("task not found")
        if task.id in self.repo.signed_up_tasks(actor.id):
            raise ConflictError("you are already signed up for this task")
        if self.repo.signups(task.id) >= task.slots:
            raise ConflictError("this task is full")
        self.repo.session.add(VolunteerSignup(task_id=task.id, user_id=actor.id))
        self.repo.session.flush()
        self.notifications.tell_org(task.org_id, "volunteer", f"{actor.name} signed up for “{task.title}”",
                                    task.id, actor.id, link="/community")

    # -- helpers --------------------------------------------------------------------------------------------------
    @staticmethod
    def _ngo(actor: User) -> uuid.UUID:
        if actor.role != "ngo" or actor.org_id is None:
            raise ForbiddenError("only NGO accounts can do this")
        return actor.org_id

    def _zone_ok(self, zone_id: uuid.UUID | None) -> None:
        if zone_id is not None and self.repo.zone(zone_id) is None:
            raise NotFoundError("zone not found")
