"""Run the full intelligence pipeline once.

Usage (from backend/):
  uv run python -m app.cli.run_pipeline                  # ingest -> classify -> geocode -> zones
  uv run python -m app.cli.run_pipeline --skip ingest    # re-process the backlog only
"""
import argparse
import json
import logging

from app.core.config import settings
from app.core.container import Container
from app.core.database import init_db


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip", nargs="*", default=[], choices=["ingest", "classify", "geocode", "zones"])
    parser.add_argument("--no-locator", action="store_true", help="disable the Amazon Location fallback")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # request URLs can carry secrets
    init_db()
    container = Container(settings, locator=None) if args.no_locator else Container(settings)
    outcome = container.run_pipeline_job(skip=set(args.skip))
    print(json.dumps(outcome.run.stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
