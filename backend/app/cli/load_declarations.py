"""Load official drought declarations from a CSV into the database.

Usage (from backend/): uv run python -m app.cli.load_declarations app/data/declarations/2026_kharif.csv
CSV columns: state_code,district,taluka,area_id,declared_on,severity,order_ref,source_url
(area_id may be empty: the taluka is then matched by name within the state and district).
"""
import csv
import sys
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.database import init_db, session_scope
from app.domain.declarations import TalukaMatcher
from app.models import AdminArea
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.declaration_repository import DeclarationRepository


def load_csv(session: Session, path: Path) -> tuple[int, list[dict]]:
    """Returns (rows loaded, rows not loaded with a reason). Never guesses a taluka or a severity."""
    areas, declarations = AdminAreaRepository(session), DeclarationRepository(session)
    matchers: dict[str, TalukaMatcher] = {}
    loaded, skipped = 0, []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["severity"] not in ("moderate", "severe"):
                skipped.append({**row, "reason": "severity must be moderate or severe"})
                continue
            area_id = int(row["area_id"]) if (row.get("area_id") or "").strip() else None
            if area_id is not None and session.get(AdminArea, area_id) is None:
                area_id = None
            if area_id is None:
                state = row["state_code"]
                matcher = matchers.setdefault(state, TalukaMatcher(areas.talukas(state)))
                hit = matcher.match(row["taluka"], district=row.get("district") or None)
                area_id = hit.area_id if hit and hit.score >= TalukaMatcher.ACCEPT else None
            if area_id is None:
                skipped.append({**row, "reason": "taluka not found"})
                continue
            declarations.upsert(area_id, row["state_code"], date.fromisoformat(row["declared_on"]), row["severity"],
                                row.get("order_ref") or None, row.get("source_url") or None)
            loaded += 1
    return loaded, skipped


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("app/data/declarations/2026_kharif.csv")
    init_db()
    with session_scope() as session:
        loaded, skipped = load_csv(session, path)
    print(f"loaded {loaded} declarations")
    for row in skipped:
        print(f"  not loaded: {row['state_code']} / {row.get('district')} / {row['taluka']}: {row['reason']}")


if __name__ == "__main__":
    main()
