"""Small column factories shared by every model module (keeps the table classes short)."""
import uuid

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import mapped_column


def pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def fk(target: str, nullable: bool = False):
    return mapped_column(UUID(as_uuid=True), ForeignKey(target, ondelete="CASCADE"),
                         nullable=nullable, index=True)


def pkfk(target: str):
    return mapped_column(UUID(as_uuid=True), ForeignKey(target, ondelete="CASCADE"), primary_key=True)


def created():
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def geometry(kind: str = "GEOMETRY"):
    return mapped_column(Geometry(kind, srid=4326), nullable=True)


def str_array():
    return mapped_column(ARRAY(String), nullable=False, server_default="{}", default=list)


def json_col(default=dict):
    return mapped_column(JSONB, default=default, server_default="[]" if default is list else "{}")
