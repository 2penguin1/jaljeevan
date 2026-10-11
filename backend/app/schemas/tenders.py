import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReliefNeedOut(BaseModel):
    people: int
    kl_per_day: float
    tanker_trips_per_day: int
    share: float
    formula: str
    suggested_price: float


MAX_PRICE = 10_000      # Rs per kL; far above any real tanker rate
MAX_QTY = 1_000_000     # kL a day
NO_INFINITY = ConfigDict(allow_inf_nan=False)  # 1e309 would be "Infinity" and break every page that shows it


class TenderIn(BaseModel):
    model_config = NO_INFINITY
    zone_id: uuid.UUID
    qty_per_day: float = Field(gt=0, le=MAX_QTY)
    duration_days: int = Field(gt=0, le=180)
    price_per_unit: float = Field(gt=0, le=MAX_PRICE)
    radius_km: float = Field(gt=0, le=500)


class TenderCreated(BaseModel):
    id: uuid.UUID


class BidActionIn(BaseModel):
    """Who acts (government or vendor) comes from the logged-in account, never from the request."""
    model_config = NO_INFINITY
    action: Literal["accept", "counter", "decline", "message"]
    expected_version: int | None = Field(default=None, ge=1)  # required for accept / counter / decline
    price_per_unit: float | None = Field(default=None, gt=0, le=MAX_PRICE)
    qty_per_day: float | None = Field(default=None, gt=0, le=MAX_QTY)
    note: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=1000)  # the message text


class RaisePriceIn(BaseModel):
    model_config = NO_INFINITY
    price_per_unit: float = Field(gt=0, le=MAX_PRICE)


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
    author: str | None = None


class BidOut(BaseModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    vendor_name: str
    distance_km: float
    rank_score: float
    reason: str
    status: str
    turn: str
    version: int
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
    waiting_for_gov: int = 0


class TenderDetail(TenderSummary):
    bids: list[BidOut]


class VendorOut(BaseModel):
    id: uuid.UUID
    name: str
    state_code: str
    tanker_count: int
    price_per_kl: float | None
    reliability: float


class InboxBid(BidOut):
    tender_id: uuid.UUID
    zone_name: str
    duration_days: int


class InboxOut(BaseModel):
    needs_action: list[InboxBid]
    waiting: list[InboxBid]
    closed: list[InboxBid]
