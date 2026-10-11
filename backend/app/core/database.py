from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def init_db(bind=engine) -> None:
    """Enable PostGIS, create every table registered on Base.metadata, then apply idempotent column patches."""
    from app import models  # noqa: F401  (importing registers the tables)
    from app.core import schema_patches

    with bind.begin() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS postgis")
    Base.metadata.create_all(bind)
    with bind.begin() as conn:
        schema_patches.apply(conn)


@contextmanager
def session_scope() -> Iterator[Session]:
    """One transaction per job (CLI run, Lambda invocation): commit on success, roll back on any error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency: same transaction rule as session_scope, one transaction per request."""
    with session_scope() as session:
        yield session
