from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import text

from app.core.database import SessionLocal
from app.domain.lifecycle import ZoneStateMachine
from app.domain.scoring import ScoringConfig
from app.domain.zones import ZoneTypeClassifier
from app.integrations.apify import ApifyClient
from app.integrations.sources.social import RedditFetcher
from app.repositories.pipeline_run_repository import PipelineRunRepository
from app.services.pipeline import IntelligencePipeline

NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)


def test_locality_inside_big_city_is_urban_pocket():
    loc = {"level": "village", "is_urban": False, "precision": "village", "district_urban": True}
    assert ZoneTypeClassifier().classify([loc]) == "urban_pocket"


def test_rural_village_stays_rural():
    loc = {"level": "village", "is_urban": False, "precision": "village", "district_urban": False}
    assert ZoneTypeClassifier().classify([loc]) == "rural"


def test_resolving_is_sticky_below_activation():
    m = ZoneStateMachine(ScoringConfig())
    assert m.next("resolving", 30, True, NOW - timedelta(hours=80), NOW, False)[0] == "resolving"
    assert m.next("resolving", 50, True, NOW, NOW, False)[0] == "resolving"
    assert m.next("resolving", 65, True, NOW, NOW, False)[0] == "active"


def test_reddit_request_limits_dates_and_drops_old_rows():
    old = {"postUrl": "https://r/1", "title": "old", "body": "water", "createdAt": "2025-01-01T00:00:00Z"}
    new = {"postUrl": "https://r/2", "title": "new", "body": "water",
           "createdAt": datetime.now(timezone.utc).isoformat()}
    apify = ApifyClient(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(201, json=[old, new]))),
                        token="t", max_usd_per_run=0.5)
    fetcher = RedditFetcher(apify, actor_id="harshmaur/reddit-scraper")
    assert fetcher.run_input()["searchTime"] == "week" and "postDateLimit" in fetcher.run_input()
    assert [i.url for i in fetcher.fetch()] == ["https://r/2"]


def test_second_concurrent_run_is_skipped(db):
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('pipeline'))"))  # a run holding the lock
    ran = []

    class Stage:
        name = "ingest"

        def run(self, ctx):
            ran.append(1)

    with SessionLocal() as other:  # a second connection must see the lock as held
        outcome = IntelligencePipeline([Stage()], PipelineRunRepository(other)).run(NOW)
        assert ran == [] and outcome.run.stats == {"skipped": "another run in progress"}
        other.rollback()
