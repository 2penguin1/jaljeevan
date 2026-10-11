import uuid
from datetime import date, datetime

from sqlalchemy import (BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint, text)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._columns import created, fk, geometry, json_col, pk, pkfk, str_array


class Signal(Base):
    """One collected post (news article, Reddit/X post, citizen report) and its classification."""

    __tablename__ = "signals"
    id: Mapped[uuid.UUID] = pk()
    source: Mapped[str] = mapped_column(String(20), index=True)  # gdelt|rss|reddit|x|citizen
    url: Mapped[str | None] = mapped_column(Text, unique=True)
    domain: Mapped[str | None] = mapped_column(String(200))
    author: Mapped[str | None] = mapped_column(String(200))
    author_user_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    title: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text, default="")
    lang: Mapped[str | None] = mapped_column(String(8))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    simhash: Mapped[int] = mapped_column(BigInteger, index=True)
    dup_of: Mapped[uuid.UUID | None] = fk("signals.id", nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending",
                                        index=True)  # pending|rejected|classified|unclear|failed
    rejected_reason: Mapped[str | None] = mapped_column(String(40))
    relevant: Mapped[bool | None] = mapped_column(Boolean)
    event_period: Mapped[str | None] = mapped_column(String(10))  # current|past|forecast|unknown
    event_date: Mapped[date | None] = mapped_column(Date)
    first_hand: Mapped[bool | None] = mapped_column(Boolean)
    english_summary: Mapped[str | None] = mapped_column(Text)
    people_affected_hint: Mapped[int | None] = mapped_column(BigInteger)
    hazards: Mapped[list[str]] = str_array()
    l1_codes: Mapped[list[str]] = str_array()
    max_severity: Mapped[int | None] = mapped_column(Integer)
    credibility: Mapped[float | None] = mapped_column(Float)
    classifier_version: Mapped[str | None] = mapped_column(String(16))
    raw_s3_key: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = json_col()
    created_at: Mapped[datetime] = created()


class SignalLabel(Base):
    __tablename__ = "signal_labels"
    signal_id: Mapped[uuid.UUID] = pkfk("signals.id")
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    l1_code: Mapped[str] = mapped_column(String(20), index=True)
    severity: Mapped[int] = mapped_column(Integer)
    evidence: Mapped[str] = mapped_column(Text)


class SignalLocation(Base):
    __tablename__ = "signal_locations"
    id: Mapped[uuid.UUID] = pk()
    signal_id: Mapped[uuid.UUID] = fk("signals.id")
    mention_text: Mapped[str] = mapped_column(String(300))
    admin_area_id: Mapped[int | None] = mapped_column(ForeignKey("admin_areas.id"))
    geom = geometry("POINT")
    precision: Mapped[str] = mapped_column(String(16))  # ward|village|town|subdistrict|district|state
    geo_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)


class SignalFeedback(Base):
    __tablename__ = "signal_feedback"
    id: Mapped[uuid.UUID] = pk()
    signal_id: Mapped[uuid.UUID] = fk("signals.id")
    user_id: Mapped[uuid.UUID] = fk("users.id")
    verdict: Mapped[str] = mapped_column(String(20))  # false|irrelevant|confirmed
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created()


class Zone(Base):
    """An affected area of any size (ward pocket … whole district) for one hazard."""

    __tablename__ = "zones"
    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(String(200))
    hazard: Mapped[str] = mapped_column(String(10), index=True)  # drought|flood|heat
    zone_type: Mapped[str] = mapped_column(String(16))  # urban_pocket|town|rural|district_wide
    geom = geometry()
    centroid = geometry("POINT")
    district_id: Mapped[int | None] = mapped_column(ForeignKey("admin_areas.id"))
    area_id: Mapped[int | None] = mapped_column(ForeignKey("admin_areas.id"))  # taluka of a footprint zone
    score: Mapped[float] = mapped_column(Float, default=0.0)
    trend: Mapped[str] = mapped_column(String(12), default="new")  # new|escalating|stable|easing
    independent_sources: Mapped[int] = mapped_column(Integer, default=0)
    population_est: Mapped[int | None] = mapped_column(BigInteger)
    population_source: Mapped[str | None] = mapped_column(String(40))
    population_urban: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(12), default="watch", index=True)
    below_resolve_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen: Mapped[datetime] = created()
    last_seen: Mapped[datetime] = created()
    __table_args__ = (Index("uq_zones_hazard_area", "hazard", "area_id", unique=True,
                            postgresql_where=text("area_id IS NOT NULL")),)


class ZoneSignal(Base):
    __tablename__ = "zone_signals"
    zone_id: Mapped[uuid.UUID] = pkfk("zones.id")
    signal_id: Mapped[uuid.UUID] = pkfk("signals.id")
    weight: Mapped[float] = mapped_column(Float)


class ZoneSnapshot(Base):
    __tablename__ = "zone_snapshots"
    id: Mapped[uuid.UUID] = pk()
    zone_id: Mapped[uuid.UUID] = fk("zones.id")
    at: Mapped[datetime] = created()
    score: Mapped[float] = mapped_column(Float)
    signal_count: Mapped[int] = mapped_column(Integer)


class ReliefBrief(Base):
    __tablename__ = "relief_briefs"
    id: Mapped[uuid.UUID] = pk()
    zone_id: Mapped[uuid.UUID] = fk("zones.id")
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(12), default="draft")  # draft|approved|rejected
    summary: Mapped[str] = mapped_column(Text, default="")
    cited_signal_ids: Mapped[list[str]] = str_array()
    population_est: Mapped[int | None] = mapped_column(BigInteger)
    lpcd_norm: Mapped[float | None] = mapped_column(Float)
    need_per_day: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(12), default="kl")
    units_per_day: Mapped[int | None] = mapped_column(Integer)
    duration_days: Mapped[int | None] = mapped_column(Integer)
    budget_inr: Mapped[float | None] = mapped_column(Float)
    suggested_price_per_unit: Mapped[float | None] = mapped_column(Float)
    price_basis: Mapped[dict] = json_col()
    short_term: Mapped[list] = json_col(list)
    long_term: Mapped[list] = json_col(list)
    reviewed_by: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created()
    __table_args__ = (UniqueConstraint("zone_id", "version"),)


class LongTermPlan(Base):
    __tablename__ = "long_term_plans"
    id: Mapped[uuid.UUID] = pk()
    zone_id: Mapped[uuid.UUID] = fk("zones.id")
    hazard: Mapped[str] = mapped_column(String(10))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(12), default="draft")  # draft|approved|sent|rejected
    title: Mapped[str] = mapped_column(String(300), default="")
    problem_summary: Mapped[str] = mapped_column(Text, default="")
    trend: Mapped[dict] = json_col()
    options: Mapped[list] = json_col(list)
    total_cost_inr: Mapped[float | None] = mapped_column(Float)
    reviewed_by: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created()


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id: Mapped[uuid.UUID] = pk()
    kind: Mapped[str] = mapped_column(String(20))  # ingest|classify|analyze|local
    started_at: Mapped[datetime] = created()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stats: Mapped[dict] = json_col()
    execution_arn: Mapped[str | None] = mapped_column(Text)
