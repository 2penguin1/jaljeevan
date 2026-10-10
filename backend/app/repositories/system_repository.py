from sqlalchemy import text
from sqlalchemy.orm import Session


def postgis_version(db: Session) -> str:
    return db.execute(text("SELECT postgis_lib_version()")).scalar_one()
