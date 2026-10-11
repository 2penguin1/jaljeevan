"""Write the declaration watch's waiting list to a CSV for a person to check.

Usage (from backend/):
  uv run python -m app.cli.declaration_review            # -> app/data/declarations/news_review.csv

Rows are talukas the news named this season but that are not declared yet (only one independent source, or a doubtful
name match). Delete the wrong rows, fill in severity if you know it, then load the rest with
  uv run python -m app.cli.load_declarations app/data/declarations/news_review.csv
"""
import csv
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.cli.extract_declarations import COLUMNS, OUT_DIR
from app.core.database import init_db, session_scope
from app.domain.text import TextFingerprinter
from app.models import AdminArea
from app.repositories.declaration_repository import DeclarationRepository
from app.repositories.declaration_source_repository import DeclarationSourceRepository
from app.services.declaration_promoter import DeclarationPromoter


def review_rows(session: Session, now: datetime) -> list[dict]:
    promoter = DeclarationPromoter(DeclarationSourceRepository(session), DeclarationRepository(session),
                                   TextFingerprinter())
    rows = []
    for mention, source, n in promoter.pending(now):
        area = session.get(AdminArea, mention.area_id)
        rows.append({"state_code": source.state_code, "district": area.district_name, "taluka": area.name,
                     "area_id": area.id, "declared_on": source.published_on.isoformat(),
                     "severity": mention.severity or "unknown",
                     "order_ref": f"news: {n} source{'s' if n != 1 else ''} (check before loading)",
                     "source_url": source.url, "confidence": mention.score, "source_text": mention.text})
    return sorted(rows, key=lambda r: (r["state_code"], r["district"] or "", r["taluka"]))


def main() -> None:
    init_db()
    out = OUT_DIR / "news_review.csv"
    with session_scope() as session:
        rows = review_rows(session, datetime.now(timezone.utc))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} talukas to check -> {out}")


if __name__ == "__main__":
    main()
