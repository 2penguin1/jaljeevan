from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, Float, ForeignKey, Index, Integer, String, UniqueConstraint
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
