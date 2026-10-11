import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ReliefNeedOut(BaseModel):
    people: int
    kl_per_day: float
    tanker_trips_per_day: int
    share: float
    formula: str
    suggested_price: float


class TenderIn(BaseModel):
    zone_id: uuid.UUID
    qty_per_day: float = Field(gt=0)
    duration_days: int = Field(gt=0, le=180)
    price_per_unit: float = Field(gt=0)
    radius_km: float = Field(gt=0, le=500)


class TenderCreated(BaseModel):
    id: uuid.UUID


class BidActionIn(BaseModel):
    side: Literal["gov", "vendor"]
    action: Literal["accept", "counter", "decline"]
    price_per_unit: float | None = Field(default=None, gt=0)
    qty_per_day: float | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=300)


class OfferOut(BaseModel):
    version: int
    price_per_unit: float
    qty_per_day: float
    proposed_by_side: str
    status: str
    note: str | None


class MessageOut(BaseModel):
    side: str
    body: str
    at: datetime


class BidOut(BaseModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    vendor_name: str
    distance_km: float
    rank_score: float
    reason: str
    status: str
    turn: str
    offer: OfferOut | None
    messages: list[MessageOut]


class TenderSummary(BaseModel):
    id: uuid.UUID
    zone_id: uuid.UUID
    zone_name: str
    status: str
    qty_per_day: float
    duration_days: int
    price_per_unit: float
    radius_km: float
    published_at: datetime | None
    committed_kl_per_day: float


class TenderDetail(TenderSummary):
    bids: list[BidOut]


class VendorOut(BaseModel):
    id: uuid.UUID
    name: str
    state_code: str
    tanker_count: int
    price_per_kl: float | None
    reliability: float
