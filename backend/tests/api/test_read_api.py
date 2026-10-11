import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, Polygon

from app.core.database import SessionLocal
from app.main import app
from app.models import (PipelineRun, Signal, SignalLabel, SignalLocation, Zone, ZoneSignal, ZoneSnapshot)

NOW = datetime.now(timezone.utc)
SQUARE = Polygon([(75.8, 17.6), (76.0, 17.6), (76.0, 17.8), (75.8, 17.8)])
TAG = "readapi"


def _signal(n: int, domain: str, title: str, created: datetime, **kw) -> Signal:
    return Signal(source="rss", url=f"https://{domain}/{TAG}/{n}", domain=domain, title=title, text="body",
                  content_hash=f"{TAG}{n}", simhash=0, status=kw.pop("status", "classified"),
                  relevant=kw.pop("relevant", True), hazards=["drought"], max_severity=4, credibility=0.8,
                  english_summary=f"summary {n}", published_at=created, created_at=created, **kw)


@pytest.fixture
def seeded():
    with SessionLocal() as s:
        z = Zone(name="Read Test Zone", hazard="drought", zone_type="rural", status="active", score=81.0,
                 trend="escalating", independent_sources=2, population_est=12000, population_urban=9000,
                 population_source="worldpop",
                 geom=from_shape(SQUARE, srid=4326), centroid=from_shape(Point(75.9, 17.7), srid=4326))
        a = _signal(1, "a.example", "<script>alert(1)</script> Taps dry", NOW - timedelta(minutes=5))
        b = _signal(2, "b.example", "Tankers late", NOW - timedelta(minutes=10))
        old = _signal(4, "d.example", "Old story ingested late", NOW - timedelta(days=3))
        old.created_at = NOW  # ingested now, published 3 days ago: must sort after a and b
        r = _signal(3, "c.example", "Cricket score", NOW - timedelta(minutes=15), status="rejected",
                    relevant=None, rejected_reason=f"{TAG}_reason")
        s.add_all([z, a, b, old, r])
        s.flush()
        s.add_all([
            SignalLabel(signal_id=a.id, code="SUPPLY_CUT", l1_code="SUPPLY", severity=4, evidence="Taps dry"),
            SignalLabel(signal_id=a.id, code="SUPPLY_TANKER", l1_code="SUPPLY", severity=2, evidence="body"),
            SignalLabel(signal_id=b.id, code="SUPPLY_TANKER", l1_code="SUPPLY", severity=3, evidence="Tankers late"),
            SignalLocation(signal_id=a.id, mention_text="Mohol", precision="village", geo_confidence=0.9,
                           geom=from_shape(Point(75.9, 17.7), srid=4326)),
            ZoneSignal(zone_id=z.id, signal_id=a.id, weight=0.6),
            ZoneSignal(zone_id=z.id, signal_id=b.id, weight=0.2),
            ZoneSnapshot(zone_id=z.id, at=NOW - timedelta(hours=2), score=70.0, signal_count=1),
            ZoneSnapshot(zone_id=z.id, at=NOW - timedelta(hours=1), score=81.0, signal_count=2),
            PipelineRun(kind=TAG, started_at=NOW, finished_at=NOW,
                        stats={"classify": {"input_tokens": 100, "output_tokens": 20}}),
        ])
        s.commit()
        ids = {"zone": str(z.id), "a": str(a.id), "b": str(b.id)}
    yield ids
    with SessionLocal() as s:
        sig_ids = [uuid.UUID(ids["a"]), uuid.UUID(ids["b"])]
        s.query(ZoneSnapshot).filter(ZoneSnapshot.zone_id == uuid.UUID(ids["zone"])).delete()
        s.query(ZoneSignal).filter(ZoneSignal.zone_id == uuid.UUID(ids["zone"])).delete()
        s.query(SignalLocation).filter(SignalLocation.signal_id.in_(sig_ids)).delete()
        s.query(SignalLabel).filter(SignalLabel.signal_id.in_(sig_ids)).delete()
        s.query(Signal).filter(Signal.content_hash.like(f"{TAG}%")).delete(synchronize_session=False)
        s.query(Zone).filter(Zone.id == uuid.UUID(ids["zone"])).delete()
        s.query(PipelineRun).filter(PipelineRun.kind == TAG).delete()
        s.commit()


def test_feed_is_newest_first_with_strongest_quote_and_cursor(seeded):
    with TestClient(app) as c:
        page = c.get("/api/v1/feed", params={"limit": 1}).json()
        first = page["items"][0]
        assert first["id"] == seeded["a"] and first["quote"] == "Taps dry" and first["place"] == "Mohol"
        assert first["zone_id"] == seeded["zone"] and page["next_cursor"]
        nxt = c.get("/api/v1/feed", params={"limit": 1, "cursor": page["next_cursor"]}).json()
        assert nxt["items"][0]["id"] == seeded["b"]
        full = c.get("/api/v1/feed").json()["items"]
        times = [i["published_at"] for i in full if i["published_at"]]
        assert times == sorted(times, reverse=True)  # newest published first, not ingest order
        assert seeded["a"] in [i["id"] for i in full] and all(i["id"] != "rejected" for i in full)


def test_feed_returns_untrusted_text_unchanged(seeded):
    with TestClient(app) as c:
        items = c.get("/api/v1/feed").json()["items"]
        assert next(i for i in items if i["id"] == seeded["a"])["title"] == "<script>alert(1)</script> Taps dry"
        assert c.get("/api/v1/feed", params={"cursor": "yesterday"}).status_code == 422


def test_zones_list_sorted_and_filtered(seeded):
    with TestClient(app) as c:
        zones = c.get("/api/v1/zones", params={"hazard": "drought"}).json()
        assert seeded["zone"] in [z["id"] for z in zones]
        mine = next(z for z in zones if z["id"] == seeded["zone"])
        assert (mine["population_urban"], mine["population_source"]) == (9000, "worldpop")
        assert [z["score"] for z in zones] == sorted((z["score"] for z in zones), reverse=True)
        assert seeded["zone"] not in [z["id"] for z in c.get("/api/v1/zones", params={"hazard": "heat"}).json()]
        assert c.get("/api/v1/zones", params={"hazard": "volcano"}).status_code == 422


def test_zone_detail_explains_the_zone(seeded):
    with TestClient(app) as c:
        d = c.get(f"/api/v1/zones/{seeded['zone']}").json()
        assert d["zone"]["name"] == "Read Test Zone" and d["zone"]["centroid"] == [75.9, 17.7]
        assert [e["signal_id"] for e in d["evidence"]] == [seeded["a"], seeded["b"]]  # by weight
        assert sum(e["weight"] for e in d["evidence"]) == pytest.approx(0.8)
        br = d["score_breakdown"]
        assert br["rule_met"] is True and br["independent_sources"] == 2
        assert sum(x["share"] for x in br["contributions"]) == pytest.approx(1.0)
        assert [t["score"] for t in d["trend"]] == [70.0, 81.0]


def test_zone_detail_errors():
    with TestClient(app) as c:
        assert c.get("/api/v1/zones/not-a-uuid").status_code == 422
        res = c.get(f"/api/v1/zones/{uuid.uuid4()}")
        assert res.status_code == 404 and res.json()["detail"].startswith("zone")


def test_stats_and_ops(seeded):
    with TestClient(app) as c:
        stats = c.get("/api/v1/stats/overview").json()
        assert stats["active_zones"] >= 1 and stats["people_affected"] >= 12000
        assert stats["posts_analysed_7d"] >= 2
        ops = c.get("/api/v1/ops/summary").json()
        assert len(ops["runs"]) <= 20 and any(r["stats"].get("classify") for r in ops["runs"])
        assert ops["totals"]["rejected_by_reason"][f"{TAG}_reason"] == 1
        assert ops["totals"]["tokens"]["input_tokens"] >= 100


def test_feed_cursor_does_not_skip_posts_that_share_a_timestamp():
    same = NOW + timedelta(days=1)  # newer than anything else, so these three are the first page(s)
    with SessionLocal() as s:
        s.add_all([_signal(10 + i, f"tie{i}.example", f"Tie {i}", same) for i in range(3)])
        s.commit()
    try:
        with TestClient(app) as c:
            first = c.get("/api/v1/feed", params={"limit": 2}).json()
            second = c.get("/api/v1/feed", params={"limit": 2, "cursor": first["next_cursor"]}).json()
            ids = [i["title"] for i in first["items"] + second["items"]]
            assert sorted(t for t in ids if t.startswith("Tie")) == ["Tie 0", "Tie 1", "Tie 2"]
    finally:
        with SessionLocal() as s:
            s.query(Signal).filter(Signal.title.like("Tie %")).delete(synchronize_session=False)
            s.commit()
