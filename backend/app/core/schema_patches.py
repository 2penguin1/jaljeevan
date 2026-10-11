"""Idempotent schema changes for databases created before a column existed.

`create_all` creates missing tables but never alters existing ones, and this project has no migration tool.
Each statement here must be safe to run on every start: new and old databases end up the same shape.
Keep the models in sync (fresh databases get these columns from `create_all` directly).
"""
from sqlalchemy import text

PATCHES: list[str] = [
    "ALTER TABLE zones ADD COLUMN IF NOT EXISTS area_id integer REFERENCES admin_areas(id)",
    "ALTER TABLE zones ADD COLUMN IF NOT EXISTS population_urban bigint",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_zones_hazard_area ON zones (hazard, area_id) WHERE area_id IS NOT NULL",
    # one pledge per person per campaign (pledging again changes the amount)
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_pledges_campaign_user ON pledges (campaign_id, user_id)",
    # 'subdistrict' needs 11 characters; only alter when still narrow, so normal starts take no lock
    """DO $$ BEGIN
         IF (SELECT character_maximum_length FROM information_schema.columns
             WHERE table_name = 'signal_locations' AND column_name = 'precision') < 16 THEN
           ALTER TABLE signal_locations ALTER COLUMN precision TYPE varchar(16);
         END IF;
       END $$""",
]


def apply(conn) -> None:
    for statement in PATCHES:
        conn.execute(text(statement))
