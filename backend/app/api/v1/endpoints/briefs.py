"""Relief briefs: an officer drafts (AI words, code numbers), then approves (publishes the tender) or rejects.
Approved briefs are public; drafts and rejected briefs are for officers only."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import ContainerDep, MaybeUser, SessionDep, require_role
from app.models import User
from app.schemas.briefs import Approved, BriefOut, RejectIn

router = APIRouter(prefix="/api/v1", tags=["briefs"])
Officer = Annotated[User, Depends(require_role("gov_admin"))]


@router.get("/zones/{zone_id}/brief")
def zone_brief(zone_id: uuid.UUID, user: MaybeUser, db: SessionDep, container: ContainerDep) -> BriefOut | None:
    brief = container.brief_service(db).latest_for_zone(zone_id, viewer=user)
    return BriefOut(**brief) if brief else None


@router.post("/zones/{zone_id}/briefs", status_code=201)
def draft_brief(zone_id: uuid.UUID, user: Officer, db: SessionDep, container: ContainerDep) -> BriefOut:
    brief = container.brief_service(db).draft(zone_id, user)
    db.commit()
    return BriefOut(**brief)


@router.get("/briefs")
def review_queue(user: Officer, db: SessionDep, container: ContainerDep) -> list[BriefOut]:
    return [BriefOut(**b) for b in container.brief_service(db).queue(user)]


@router.get("/briefs/{brief_id}")
def get_brief(brief_id: uuid.UUID, user: MaybeUser, db: SessionDep, container: ContainerDep) -> BriefOut:
    return BriefOut(**container.brief_service(db).get(brief_id, viewer=user))


@router.post("/briefs/{brief_id}/approve")
def approve(brief_id: uuid.UUID, user: Officer, db: SessionDep, container: ContainerDep) -> Approved:
    tender_id = container.brief_service(db).approve(brief_id, user)
    db.commit()
    return Approved(tender_id=tender_id)


@router.post("/briefs/{brief_id}/reject", status_code=204)
def reject(brief_id: uuid.UUID, body: RejectIn, user: Officer, db: SessionDep, container: ContainerDep) -> None:
    container.brief_service(db).reject(brief_id, user, body.notes)
    db.commit()
