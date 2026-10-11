import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BriefAction(BaseModel):
    key: str
    text: str


class BriefOut(BaseModel):
    id: uuid.UUID
    zone_id: uuid.UUID
    zone_name: str
    version: int
    status: str
    summary: str
    actions: list[BriefAction]
    cited_signal_ids: list[str]
    people: int | None
    need_per_day: float | None
    units_per_day: int | None
    duration_days: int | None
    budget_inr: float | None
    suggested_price_per_unit: float | None
    formula: str
    written_by: str
    review_notes: str | None
    created_at: datetime


class RejectIn(BaseModel):
    notes: str = Field(default="", max_length=500)


class Approved(BaseModel):
    tender_id: uuid.UUID
