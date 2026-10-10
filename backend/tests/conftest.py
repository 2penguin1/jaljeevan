import os

# Point the app at the test database BEFORE any app module creates the engine.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://jal:jal@localhost:5433/jal_test"
)

import pytest  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import Base, engine, init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    init_db(engine)
    Base.metadata.drop_all(engine)
    init_db(engine)
    yield


@pytest.fixture
def db():
    """A session whose work is rolled back after each test."""
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    trans.rollback()
    conn.close()
