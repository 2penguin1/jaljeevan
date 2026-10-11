import uuid
from datetime import date, datetime

from sqlalchemy import Date, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._columns import created, fk, pk, pkfk


class Reaction(Base):
    __tablename__ = "reactions"
    signal_id: Mapped[uuid.UUID] = pkfk("signals.id")
    user_id: Mapped[uuid.UUID] = pkfk("users.id")
    kind: Mapped[str] = mapped_column(String(16))  # same_here|water_arrived|not_arrived
    created_at: Mapped[datetime] = created()


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[uuid.UUID] = pk()
    signal_id: Mapped[uuid.UUID] = fk("signals.id")
    user_id: Mapped[uuid.UUID] = fk("users.id")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created()


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[uuid.UUID] = pk()
    ngo_org_id: Mapped[uuid.UUID] = fk("organizations.id")
    zone_id: Mapped[uuid.UUID | None] = fk("zones.id", nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    story: Mapped[str] = mapped_column(Text, default="")
    goal_inr: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(12), default="active")
    created_at: Mapped[datetime] = created()


class Pledge(Base):
    """A pledge only: no real payment is processed (stated in the UI)."""

    __tablename__ = "pledges"
    id: Mapped[uuid.UUID] = pk()
    campaign_id: Mapped[uuid.UUID] = fk("campaigns.id")
    user_id: Mapped[uuid.UUID] = fk("users.id")
    amount_inr: Mapped[float] = mapped_column(Float)
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created()
    __table_args__ = (UniqueConstraint("campaign_id", "user_id"),)  # one pledge per person per campaign


class VolunteerTask(Base):
    __tablename__ = "volunteer_tasks"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = fk("organizations.id")
    zone_id: Mapped[uuid.UUID | None] = fk("zones.id", nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    task_date: Mapped[date | None] = mapped_column(Date)
    slots: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = created()


class VolunteerSignup(Base):
    __tablename__ = "volunteer_signups"
    task_id: Mapped[uuid.UUID] = pkfk("volunteer_tasks.id")
    user_id: Mapped[uuid.UUID] = pkfk("users.id")
    created_at: Mapped[datetime] = created()
