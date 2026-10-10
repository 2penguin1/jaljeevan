from datetime import datetime, timezone

import httpx
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, Polygon
from sqlalchemy import select

from app.core.config import Settings
from app.core.container import Container
from app.domain.classification import BatchResult, Label, LocationMention, PostResult
from app.domain.entities import RawItem
from app.domain.events import SignalClassified, ZoneEscalated
from app.integrations.archive import LocalRawArchive
from app.integrations.ports import LLMResult
from app.integrations.sources.registry import FetcherRegistry
from app.models import AdminArea, Signal, SignalFeedback, User, Zone
from app.repositories.signal_repository import SignalRepository

NOW = datetime.now(timezone.utc)
TEXT = "Residents of Mahadevapura say there has been no water for 11 days and tankers cost double."


class EchoLLM:
    """Labels every post in a batch as a severe Mahadevapura drought report."""

    def parse(self, *, system, user, schema, max_tokens):
        n = user.count("<post id=")
        results = [PostResult(id=str(i), relevant=True, event_period="current", event_date=None, first_hand=False,
                              labels=[Label(code="SUPPLY.DRY_TAPS", severity=4, evidence="no water for 11 days")],
                              locations=[LocationMention(mention="Mahadevapura", state_hint="Karnataka",
                                                         district_hint="Bangalore Urban", precision="ward")],
                              people_affected_hint=None, english_summary="Dry taps.") for i in range(n)]
        return LLMResult(parsed=BatchResult(results=results), usage={"input_tokens": 10, "output_tokens": 5})


class FakeFetcher:
    def __init__(self, name, items, fail=False):
        self.name, self.items, self.fail, self.enabled = name, items, fail, True

    def fetch(self):
        if self.fail:
            from app.core.exceptions import ExternalServiceError
            raise ExternalServiceError(self.name, "down")
        return self.items


def seed(db):
    db.add_all([
        AdminArea(level="district", name="Bangalore Urban", name_norm="bangalore urban", state_code="KA",
                  district_name="Bangalore Urban",
                  geom=from_shape(Polygon([(77.4, 12.8), (77.8, 12.8), (77.8, 13.2), (77.4, 13.2)]), srid=4326)),
        AdminArea(level="ward", name="Mahadevapura", name_norm="mahadevapura", state_code="KA", is_urban=True,
                  population=60000, district_name="Bangalore Urban", geom=from_shape(Point(77.69, 12.99), srid=4326)),
    ])
    db.flush()


def container(tmp_path, fetchers) -> Container:
    registry = FetcherRegistry()
    for f in fetchers:
        registry.register(f)
    offline = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    return Container(Settings(), llm=EchoLLM(), locator=None, registry=registry,
                     archive=LocalRawArchive(tmp_path), http=offline)


def news():
    return [RawItem(source="gdelt", url="https://thehindu.com/x", title="Taps dry", text=TEXT, published_at=NOW,
                    domain="thehindu.com", country="IN"),
            RawItem(source="gdelt", url="https://deccanherald.com/y", title="Bengaluru ward thirsty",
                    text="Mahadevapura: no water for 11 days, say residents queuing at tankers since dawn.",
                    published_at=NOW, domain="deccanherald.com", country="IN")]


def test_pipeline_end_to_end_with_events(db, tmp_path):
    seed(db)
    c = container(tmp_path, [FakeFetcher("gdelt", news()), FakeFetcher("x", [], fail=True)])
    outcome = c.pipeline(db).run(NOW)
    stats = outcome.run.stats
    assert outcome.run.finished_at is not None
    assert stats["ingest"]["gdelt"]["inserted"] == 2
    assert stats["ingest"]["x"] == {"error": "x: down"}          # one broken source is isolated
    assert stats["classify"]["classified"] == 2 and stats["geocode"]["located"] == 2
    assert stats["zones"]["created"] == 1
    zone = db.scalar(select(Zone))
    assert zone.status == "active" and zone.zone_type == "urban_pocket"
    assert sum(isinstance(e, SignalClassified) for e in outcome.events) == 2
    assert [e.zone_id for e in outcome.events if isinstance(e, ZoneEscalated)] == [zone.id]


def test_pipeline_can_skip_ingest_and_drain_backlog(db, tmp_path):
    seed(db)
    db.add(Signal(source="rss", url="https://b/1", title="t", text=TEXT, content_hash="b1", simhash=0))
    db.flush()
    outcome = container(tmp_path, []).pipeline(db).run(NOW, skip={"ingest"})
    assert "ingest" not in outcome.run.stats and outcome.run.stats["classify"]["classified"] == 1


def test_recent_contrasts_come_from_reviewer_feedback(db):
    s = Signal(source="rss", url="https://c/1", title="Water polo final", text="x", content_hash="c1", simhash=0,
               english_summary="A water polo match result.")
    u = User(email="gov@x", password_hash="x", name="g", role="gov_admin")
    db.add_all([s, u])
    db.flush()
    db.add(SignalFeedback(signal_id=s.id, user_id=u.id, verdict="irrelevant"))
    db.flush()
    assert SignalRepository(db).recent_contrasts() == ["A water polo match result."]
