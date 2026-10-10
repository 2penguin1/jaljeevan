import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._columns import created, fk, geometry, json_col, pk


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = pk()
    kind: Mapped[str] = mapped_column(String(12), index=True)  # government|vendor|ngo
    name: Mapped[str] = mapped_column(String(200))
    state_code: Mapped[str] = mapped_column(String(4))
    geom = geometry("POINT")
    tanker_count: Mapped[int] = mapped_column(Integer, default=0)
    tanker_capacity_kl: Mapped[float] = mapped_column(Float, default=10.0)
    base_price_per_kl: Mapped[float | None] = mapped_column(Float)
    reliability: Mapped[float] = mapped_column(Float, default=0.8)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(200))


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(12), index=True)  # gov_admin|vendor|ngo|citizen
    org_id: Mapped[uuid.UUID | None] = fk("organizations.id", nullable=True)
    sns_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created()


class Tender(Base):
    __tablename__ = "tenders"
    id: Mapped[uuid.UUID] = pk()
    zone_id: Mapped[uuid.UUID] = fk("zones.id")
    brief_id: Mapped[uuid.UUID | None] = fk("relief_briefs.id", nullable=True)
    gov_org_id: Mapped[uuid.UUID] = fk("organizations.id")
    created_by: Mapped[uuid.UUID] = fk("users.id")
    resource_type: Mapped[str] = mapped_column(String(20), default="water_tanker")
    unit: Mapped[str] = mapped_column(String(12), default="kl")
    qty_per_day: Mapped[float] = mapped_column(Float)
    duration_days: Mapped[int] = mapped_column(Integer)
    price_per_unit: Mapped[float] = mapped_column(Float)
    radius_km: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(12), default="draft")  # draft|published|closed|cancelled
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = created()


class Bid(Base):
    __tablename__ = "bids"
    id: Mapped[uuid.UUID] = pk()
    tender_id: Mapped[uuid.UUID] = fk("tenders.id")
    vendor_org_id: Mapped[uuid.UUID] = fk("organizations.id")
    distance_km: Mapped[float] = mapped_column(Float)
    rank_score: Mapped[float] = mapped_column(Float, default=0.0)
    rank_reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="invited")
    turn: Mapped[str] = mapped_column(String(8), default="vendor")  # gov|vendor|none
    current_offer_version: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = created()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())
    __table_args__ = (UniqueConstraint("tender_id", "vendor_org_id"),)


class BidOffer(Base):
    __tablename__ = "bid_offers"
    id: Mapped[uuid.UUID] = pk()
    bid_id: Mapped[uuid.UUID] = fk("bids.id")
    version: Mapped[int] = mapped_column(Integer)
    price_per_unit: Mapped[float] = mapped_column(Float)
    qty_per_day: Mapped[float] = mapped_column(Float)
    proposed_by_side: Mapped[str] = mapped_column(String(8))  # gov|vendor
    proposed_by: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="proposed")  # proposed|agreed|superseded|rejected
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created()
    __table_args__ = (UniqueConstraint("bid_id", "version"),)


class BidMessage(Base):
    __tablename__ = "bid_messages"
    id: Mapped[uuid.UUID] = pk()
    bid_id: Mapped[uuid.UUID] = fk("bids.id")
    author_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    side: Mapped[str] = mapped_column(String(8))  # gov|vendor|system
    body: Mapped[str] = mapped_column(Text)
    offer_id: Mapped[uuid.UUID | None] = fk("bid_offers.id", nullable=True)
    created_at: Mapped[datetime] = created()


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = json_col()
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created()
