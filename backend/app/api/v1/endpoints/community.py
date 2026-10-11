"""NGO campaigns (pledges only, no money taken) and volunteer tasks. Reading is open; writing needs an account
(starting campaigns and posting tasks needs an NGO account)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import CurrentUser, MaybeUser, SessionDep, require_role
from app.models import User
from app.repositories.community_repository import CommunityRepository
from app.schemas.community import CampaignIn, CampaignOut, Created, PledgeIn, TaskIn, TaskOut
from app.services.community_service import CommunityService

router = APIRouter(prefix="/api/v1", tags=["community"])
Ngo = Annotated[User, Depends(require_role("ngo"))]


def _service(db) -> CommunityService:
    return CommunityService(CommunityRepository(db))


@router.get("/campaigns")
def campaigns(db: SessionDep, zone_id: uuid.UUID | None = None) -> list[CampaignOut]:
    return [CampaignOut(**c) for c in _service(db).campaigns(zone_id)]


@router.post("/campaigns", status_code=201)
def start_campaign(body: CampaignIn, user: Ngo, db: SessionDep) -> Created:
    cid = _service(db).start_campaign(user, body.zone_id, body.title, body.story, body.goal_inr)
    db.commit()
    return Created(id=cid)


@router.post("/campaigns/{campaign_id}/pledges", status_code=204)
def pledge(campaign_id: uuid.UUID, body: PledgeIn, user: CurrentUser, db: SessionDep) -> None:
    _service(db).pledge(user, campaign_id, body.amount_inr, body.message)
    db.commit()


@router.get("/volunteer-tasks")
def tasks(user: MaybeUser, db: SessionDep, zone_id: uuid.UUID | None = None) -> list[TaskOut]:
    return [TaskOut(**t) for t in _service(db).tasks(zone_id, viewer=user)]


@router.post("/volunteer-tasks", status_code=201)
def post_task(body: TaskIn, user: Ngo, db: SessionDep) -> Created:
    tid = _service(db).post_task(user, body.zone_id, body.title, body.description, body.task_date, body.slots)
    db.commit()
    return Created(id=tid)


@router.post("/volunteer-tasks/{task_id}/signups", status_code=204)
def sign_up(task_id: uuid.UUID, user: CurrentUser, db: SessionDep) -> None:
    _service(db).sign_up(user, task_id)
    db.commit()
