import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

NO_INFINITY = ConfigDict(allow_inf_nan=False)


class CampaignIn(BaseModel):
    model_config = NO_INFINITY
    zone_id: uuid.UUID | None = None
    title: str = Field(min_length=3, max_length=300)
    story: str = Field(default="", max_length=4000)
    goal_inr: float = Field(gt=0, le=1_000_000_000)


class PledgeIn(BaseModel):
    """A pledge only: no payment is taken."""
    model_config = NO_INFINITY
    amount_inr: float = Field(gt=0, le=10_000_000)
    message: str | None = Field(default=None, max_length=500)


class TaskIn(BaseModel):
    zone_id: uuid.UUID | None = None
    title: str = Field(min_length=3, max_length=300)
    description: str = Field(default="", max_length=2000)
    task_date: date | None = None
    slots: int = Field(gt=0, le=1000)


class Created(BaseModel):
    id: uuid.UUID


class CampaignOut(BaseModel):
    id: uuid.UUID
    title: str
    story: str
    goal_inr: float
    pledged_inr: float
    pledges: int
    zone_id: uuid.UUID | None
    zone_name: str | None
    ngo_name: str
    created_at: datetime


class TaskOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    task_date: date | None
    slots: int
    taken: int
    signed_up: bool
    zone_id: uuid.UUID | None
    zone_name: str | None
    ngo_name: str
