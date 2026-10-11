"""Recompute every classified signal's hazards from its stored categories (no AI calls).

Run after changing which hazards a taxonomy category maps to: `uv run python -m app.cli.retag_hazards`
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import init_db, session_scope
from app.domain.taxonomy import Taxonomy
from app.models import Signal


def retag(session: Session, taxonomy: Taxonomy | None = None) -> int:
    """Returns how many signals changed."""
    taxonomy = taxonomy or Taxonomy.load()
    changed = 0
    for signal in session.scalars(select(Signal).where(Signal.status == "classified")):
        hazards = taxonomy.hazards_for(signal.l1_codes or [])
        if hazards != list(signal.hazards or []):
            signal.hazards = hazards
            changed += 1
    session.flush()
    return changed


def main() -> None:
    init_db()
    with session_scope() as session:
        print(f"retagged {retag(session)} signals")


if __name__ == "__main__":
    main()
