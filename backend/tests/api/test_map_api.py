from datetime import datetime, timezone
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, Polygon
from app.core.database import SessionLocal
from app.main import app
from app.models import AdminArea, DistrictIndicator, Signal, SignalLocation, Zone

SQUARE = Polygon([(77.4, 12.8), (77.8, 12.8), (77.8, 13.2), (77.4, 13.2)])

def seed():
    with SessionLocal() as s:
        d = AdminArea(level="district", name="Bangalore Urban", name_norm="bangalore urban", state_code="KA",
                      geom=from_shape(SQUARE, srid=4326))
        s.add(d); s.flush()
        s.add(DistrictIndicator(district_id=d.id, period=datetime.now(timezone.utc).date(),
                                rainfall_departure_pct=-55, source="imd"))
        z = Zone(name="Map Test Zone", hazard="drought", zone_type="urban_pocket", status="active", score=72.5,
                 geom=from_shape(SQUARE.buffer(-0.1), srid=4326), centroid=from_shape(Point(77.6, 13.0), srid=4326))
        s.add(z)
        sig = Signal(source="rss", url="https://map.test/1", title="<b>Taps dry</b>", text="x", content_hash="map1",
                     simhash=0, status="classified", relevant=True, hazards=["drought"], max_severity=4,
                     published_at=datetime.now(timezone.utc))
        s.add(sig); s.flush()
        s.add(SignalLocation(signal_id=sig.id, mention_text="Mahadevapura", precision="ward", geo_confidence=0.9,
                             geom=from_shape(Point(77.69, 12.99), srid=4326)))
        s.commit()
        return str(z.id), d.id

def cleanup(zone_id, district_id):
    with SessionLocal() as s:
        s.query(SignalLocation).filter(SignalLocation.mention_text == "Mahadevapura").delete()
        s.query(Signal).filter(Signal.url == "https://map.test/1").delete()
        s.query(Zone).filter(Zone.name == "Map Test Zone").delete()
        s.query(DistrictIndicator).filter(DistrictIndicator.district_id == district_id).delete()
        s.query(AdminArea).filter(AdminArea.id == district_id).delete()
        s.commit()

def test_map_endpoints_return_geojson():
    zone_id, district_id = seed()
    try:
        with TestClient(app) as c:
            zones = c.get("/api/v1/map/zones", params={"hazard": "drought"}).json()
            f = next(f for f in zones["features"] if f["id"] == zone_id)
            assert f["properties"]["score"] == 72.5 and f["geometry"]["type"] in ("Polygon", "MultiPolygon")
            assert f["properties"]["centroid"] == [77.6, 13.0]
            districts = c.get("/api/v1/map/districts", params={"hazard": "drought"}).json()
            blr = next(f for f in districts["features"] if f["properties"]["id"] == district_id)
            assert blr["properties"]["band"] == "severe" and blr["properties"]["indicator_value"] == -55
            signals = c.get("/api/v1/map/signals", params={"hazard": "drought", "hours": 48}).json()
            s = next(f for f in signals["features"] if f["properties"]["title"] == "<b>Taps dry</b>")
            assert s["geometry"]["coordinates"] == [77.69, 12.99] and s["properties"]["severity"] == 4
    finally:
        cleanup(zone_id, district_id)

def test_map_rejects_unknown_hazard_and_handles_empty():
    with TestClient(app) as c:
        assert c.get("/api/v1/map/zones", params={"hazard": "volcano"}).status_code == 422
        empty = c.get("/api/v1/map/zones", params={"hazard": "heat"}).json()
        assert empty["type"] == "FeatureCollection" and isinstance(empty["features"], list)
