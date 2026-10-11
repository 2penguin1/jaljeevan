"""Long-term plans: an officer drafts (menu options, code costs, AI words), approves or rejects.
Approved plans are public (and printable); drafts are for officers only."""
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.dependencies import ContainerDep, MaybeUser, SessionDep, require_role
from app.models import User

router = APIRouter(prefix="/api/v1", tags=["plans"])
Officer = Annotated[User, Depends(require_role("gov_admin"))]


class PlanOptionOut(BaseModel):
    key: str
    label: str
    unit: str
    quantity: int
    unit_cost_inr: int
    cost_inr: int
    basis: str


class PlanTrend(BaseModel):
    first_score: float | None = None
    last_score: float | None = None
    since: str | None = None
    points: int = 0


class PlanOut(BaseModel):
    id: uuid.UUID
    zone_id: uuid.UUID
    zone_name: str
    hazard: str
    version: int
    status: str
    title: str
    problem_summary: str
    options: list[PlanOptionOut]
    total_cost_inr: float | None
    written_by: str
    trend: PlanTrend
    review_notes: str | None
    created_at: datetime


class PlanRejectIn(BaseModel):
    notes: str = Field(default="", max_length=500)


@router.get("/zones/{zone_id}/plan")
def zone_plan(zone_id: uuid.UUID, user: MaybeUser, db: SessionDep, container: ContainerDep) -> PlanOut | None:
    plan = container.plan_service(db).latest_for_zone(zone_id, viewer=user)
    return PlanOut(**plan) if plan else None


@router.post("/zones/{zone_id}/plans", status_code=201)
def draft_plan(zone_id: uuid.UUID, user: Officer, db: SessionDep, container: ContainerDep) -> PlanOut:
    plan = container.plan_service(db).draft(zone_id, user)
    db.commit()
    return PlanOut(**plan)


@router.get("/plans")
def plan_queue(user: Officer, db: SessionDep, container: ContainerDep) -> list[PlanOut]:
    return [PlanOut(**p) for p in container.plan_service(db).queue(user)]


@router.get("/plans/{plan_id}")
def get_plan(plan_id: uuid.UUID, user: MaybeUser, db: SessionDep, container: ContainerDep) -> PlanOut:
    return PlanOut(**container.plan_service(db).get(plan_id, viewer=user))


@router.post("/plans/{plan_id}/approve", status_code=204)
def approve_plan(plan_id: uuid.UUID, user: Officer, db: SessionDep, container: ContainerDep) -> None:
    container.plan_service(db).approve(plan_id, user)
    db.commit()


@router.post("/plans/{plan_id}/reject", status_code=204)
def reject_plan(plan_id: uuid.UUID, body: PlanRejectIn, user: Officer, db: SessionDep, container: ContainerDep) -> None:
    container.plan_service(db).reject(plan_id, user, body.notes)
    db.commit()
