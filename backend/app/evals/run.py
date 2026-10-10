"""Run the real classifier on the hand-labelled gold set (inside a rolled-back transaction) and report metrics.

Usage (from backend/): uv run python -m app.evals.run      # exits non-zero if below target
"""
import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.container import Container
from app.core.database import engine
from app.evals.metrics import EvalScorer
from app.integrations.dates import parse_dt
from app.models import Signal

GOLD = Path(__file__).parent / "gold.jsonl"


class EvalRunner:
    def __init__(self, container: Container, scorer: EvalScorer):
        self.container = container
        self.scorer = scorer

    def run(self, gold: list[dict], session: Session) -> tuple[dict, dict]:
        signals = [Signal(source=g.get("source", "gdelt"), url=f"https://eval.local/{uuid.uuid4()}",
                          title=g.get("title", ""), text=g["text"], content_hash=uuid.uuid4().hex, simhash=0,
                          published_at=parse_dt(g.get("published_at"))) for g in gold]
        session.add_all(signals)
        session.flush()
        stats = self.container.classification_service(session).classify([s.id for s in signals])
        geocoder = self.container.geocoding_service(session)
        pairs = []
        for g, s in zip(gold, signals):
            session.refresh(s)
            geocoder.geocode(s)
            loc = session.execute(text("SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon FROM signal_locations "
                                       "WHERE signal_id = :i AND geom IS NOT NULL "
                                       "ORDER BY geo_confidence DESC LIMIT 1"), {"i": s.id}).first()
            pairs.append((g["expected"], {"relevant": bool(s.relevant) and s.status == "classified",
                                          "event_period": s.event_period, "l1": s.l1_codes,
                                          "severity": s.max_severity,
                                          "lat": loc.lat if loc else None, "lon": loc.lon if loc else None}))
        return self.scorer.score(pairs), stats.as_dict()


def main() -> None:
    gold = [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not gold:
        sys.exit("gold.jsonl is empty: run `python -m app.evals.export` and label the candidates first")
    scorer = EvalScorer()
    conn = engine.connect()
    trans = conn.begin()
    try:
        metrics, stats = EvalRunner(Container(settings), scorer).run(gold, Session(bind=conn))
    finally:
        trans.rollback()  # evaluation never leaves rows behind
        conn.close()
    print(json.dumps({"metrics": metrics, "llm": stats}, indent=2))
    failed = scorer.failed_targets(metrics)
    if failed:
        sys.exit(f"below target: {failed}")


if __name__ == "__main__":
    main()
