from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import inspect, select

from app.core.database import engine
from app.models import AdminArea, Signal, SignalLocation

EXPECTED = {
    "admin_areas", "district_indicators", "source_domains", "geocode_cache", "signals",
    "signal_labels", "signal_locations", "signal_feedback", "zones", "zone_signals",
    "zone_snapshots", "relief_briefs", "long_term_plans", "pipeline_runs", "organizations",
    "users", "tenders", "bids", "bid_offers", "bid_messages", "notifications", "reactions",
    "comments", "campaigns", "pledges", "volunteer_tasks", "volunteer_signups",
}


def test_all_tables_exist():
    assert EXPECTED <= set(inspect(engine).get_table_names())


def test_signal_with_point_location_roundtrips(db):
    area = AdminArea(level="town", name="Barmer", name_norm="barmer", state_code="RJ",
                     population=100000, geom=from_shape(Point(71.39, 25.75), srid=4326))
    db.add(area)
    sig = Signal(source="gdelt", url="https://x.test/a", title="t", text="no water",
                 content_hash="h1", simhash=1)
    db.add(sig)
    db.flush()
    db.add(SignalLocation(signal_id=sig.id, mention_text="Barmer", admin_area_id=area.id,
                          geom=from_shape(Point(71.39, 25.75), srid=4326),
                          precision="town", geo_confidence=0.9))
    db.flush()
    db.expire_all()
    got = db.scalar(select(Signal).where(Signal.url == "https://x.test/a"))
    assert got.status == "pending"
    assert got.hazards == [] and got.l1_codes == []
