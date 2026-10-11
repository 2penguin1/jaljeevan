from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._columns import geometry


class AdminArea(Base):
    """Gazetteer: districts (polygons) and towns / villages / wards (points or polygons)."""

    __tablename__ = "admin_areas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(16), index=True)  # state|district|town|ward|village
    name: Mapped[str] = mapped_column(String(200))
    name_norm: Mapped[str] = mapped_column(String(200), index=True)
    aliases_norm: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}", default=list)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("admin_areas.id"))
    state_code: Mapped[str] = mapped_column(String(4), index=True)
    district_name: Mapped[str | None] = mapped_column(String(200))
    is_urban: Mapped[bool] = mapped_column(Boolean, default=False)
    population: Mapped[int | None] = mapped_column(BigInteger)
    geom = geometry()
    __table_args__ = (Index("ix_admin_areas_aliases_norm", "aliases_norm", postgresql_using="gin"),)


class DistrictIndicator(Base):
    """Daily/seasonal hazard indicators per district (IMD rainfall, Open-Meteo heat & rain)."""

    __tablename__ = "district_indicators"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("admin_areas.id"), index=True)
    period: Mapped[date] = mapped_column(Date)
    rainfall_departure_pct: Mapped[float | None] = mapped_column(Float)
    drought_index: Mapped[float | None] = mapped_column(Float)
    tmax_c: Mapped[float | None] = mapped_column(Float)
    apparent_tmax_c: Mapped[float | None] = mapped_column(Float)
    precip_mm_24h: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40))
    __table_args__ = (UniqueConstraint("district_id", "period", "source"),)


class AreaIndicator(Base):
    """Measured values per area (taluka) and period, one row per metric: SPI, soil anomaly, people in dry areas.
    A long table, so a new data source needs no schema change."""

    __tablename__ = "area_indicators"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("admin_areas.id"), index=True)
    period: Mapped[date] = mapped_column(Date)  # last day the value covers
    source: Mapped[str] = mapped_column(String(40))  # chirps-spi | gdo-soil | ...
    metric: Mapped[str] = mapped_column(String(40))
    value: Mapped[float] = mapped_column(Float)
    __table_args__ = (UniqueConstraint("area_id", "period", "source", "metric"),
                      Index("ix_area_indicators_source_period", "source", "period"))


class DroughtDeclaration(Base):
    """An official state drought declaration for one taluka (Government Resolution / revenue order)."""

    __tablename__ = "drought_declarations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("admin_areas.id"), index=True)
    state_code: Mapped[str] = mapped_column(String(4))
    declared_on: Mapped[date] = mapped_column(Date)
    severity: Mapped[str] = mapped_column(String(12))  # moderate | severe
    order_ref: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("area_id", "declared_on"),)


class DeclarationSource(Base):
    """One news article or official PDF the declaration watch read (read once; failed ones get one retry)."""

    __tablename__ = "declaration_sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(Text, unique=True)
    domain: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(12))  # news | official
    state_code: Mapped[str | None] = mapped_column(String(4))  # boundary pool of the talukas it named
    title: Mapped[str | None] = mapped_column(Text)
    published_on: Mapped[date] = mapped_column(Date)
    # listed | no_list | not_declaration | state_unclear | failed | blocked
    status: Mapped[str] = mapped_column(String(20), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    list_fingerprint: Mapped[int | None] = mapped_column(BigInteger)  # simhash of its list sentences (wire copies)


class DeclarationMention(Base):
    """A taluka named as declared by one source: the 'who said what' record behind every news-based declaration."""

    __tablename__ = "declaration_mentions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("declaration_sources.id", ondelete="CASCADE"), index=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("admin_areas.id"), index=True)
    score: Mapped[float] = mapped_column(Float)
    severity: Mapped[str | None] = mapped_column(String(12))  # moderate | severe | None = not stated
    text: Mapped[str] = mapped_column(Text)  # the name as written
    __table_args__ = (UniqueConstraint("source_id", "area_id"),)


class SourceDomain(Base):
    """Credibility tier for a news domain (official 1.0 / national 0.8 / regional 0.7)."""

    __tablename__ = "source_domains"
    domain: Mapped[str] = mapped_column(String(200), primary_key=True)
    tier: Mapped[str] = mapped_column(String(20))
    credibility: Mapped[float] = mapped_column(Float)


class GeocodeCache(Base):
    __tablename__ = "geocode_cache"
    query: Mapped[str] = mapped_column(String(400), primary_key=True)
    result: Mapped[dict] = mapped_column(JSONB)
