"""Run the declaration watch once: read new declaration news (other states), then apply the safety rule.

Usage (from backend/):
  uv run python -m app.cli.watch_declarations           # skips if it ran less than 20 hours ago
  uv run python -m app.cli.watch_declarations --force   # run now anyway

It also runs inside every pipeline run (stage "watch"). Then: uv run python -m app.cli.declaration_review
"""
import argparse
import json
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.container import Container
from app.core.database import init_db, session_scope
from app.repositories.pipeline_run_repository import PipelineRunRepository
from app.services.pipeline import PipelineContext


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="ignore the 20-hour gap")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    init_db()
    container = Container(settings, locator=None)
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        runs = PipelineRunRepository(session)  # recorded like a pipeline run, so the 20-hour gap sees it
        run = runs.start("watch", now)
        ctx = PipelineContext(now=now, run_id=str(run.id))
        container.declaration_watch_stage(session, force=args.force).run(ctx)
        runs.finish(run, ctx.stats, datetime.now(timezone.utc))
    print(json.dumps(ctx.stats, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
