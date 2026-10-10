"""Export a random sample of crawled posts for hand-labelling.

Usage (from backend/): uv run python -m app.evals.export --n 60
Then fill each line's "expected" and append the lines to app/evals/gold.jsonl.
"""
import argparse
import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import session_scope
from app.models import Signal

OUT = Path(__file__).parent / "candidates.jsonl"


class GoldSetExporter:
    def __init__(self, session: Session):
        self.session = session

    def export(self, n: int, out: Path = OUT) -> int:
        rows = self.session.scalars(select(Signal).where(Signal.status.in_(("classified", "unclear", "pending")))
                                    .order_by(func.random()).limit(n)).all()
        with out.open("w", encoding="utf-8") as fh:
            for s in rows:
                fh.write(json.dumps({
                    "title": s.title, "text": s.text, "source": s.source,
                    "published_at": s.published_at.isoformat() if s.published_at else None,
                    "expected": {"relevant": None, "event_period": None, "l1": [], "severity": None,
                                 "lat": None, "lon": None}}, ensure_ascii=False) + "\n")
        return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=60)
    args = parser.parse_args()
    with session_scope() as session:
        count = GoldSetExporter(session).export(args.n)
    print(f"wrote {count} candidates to {OUT}")


if __name__ == "__main__":
    main()
