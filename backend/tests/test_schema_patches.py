from sqlalchemy import text

from app.core import schema_patches
from app.core.database import engine


def _columns(conn, table):
    return {r.column_name: r for r in conn.execute(text(
        "SELECT column_name, character_maximum_length FROM information_schema.columns WHERE table_name = :t"),
        {"t": table})}


def test_patches_upgrade_an_old_database_and_are_safe_to_repeat():
    with engine.connect() as conn:
        trans = conn.begin()  # everything below is rolled back: DDL is transactional in Postgres
        try:
            # shape of a database created before these columns existed
            conn.execute(text("DROP INDEX IF EXISTS uq_zones_hazard_area"))
            conn.execute(text("ALTER TABLE zones DROP COLUMN IF EXISTS area_id, DROP COLUMN IF EXISTS population_urban"))
            conn.execute(text("ALTER TABLE signal_locations ALTER COLUMN precision TYPE varchar(10)"))
            schema_patches.apply(conn)
            schema_patches.apply(conn)  # second run must be a no-op, not an error
            zones = _columns(conn, "zones")
            assert {"area_id", "population_urban"} <= set(zones)
            assert _columns(conn, "signal_locations")["precision"].character_maximum_length == 16
            assert conn.scalar(text("SELECT count(*) FROM pg_indexes WHERE indexname = 'uq_zones_hazard_area'")) == 1
        finally:
            trans.rollback()
