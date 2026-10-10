from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def init_db(bind=engine) -> None:
    """Enable PostGIS and create every table registered on Base.metadata."""
    from app import models  # noqa: F401  (importing registers the tables)

    with bind.begin() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS postgis")
    Base.metadata.create_all(bind)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
