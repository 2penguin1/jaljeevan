from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, box

from app.core.database import SessionLocal
from app.main import app
from app.models import AdminArea, AreaIndicator, DroughtDeclaration, Zone

NOW = datetime.now(timezone.utc)
PERIOD = (NOW - timedelta(days=3)).date()


@pytest.fixture
def drought_zone():
    with SessionLocal() as s:
        district = AdminArea(level="district", name="Solapur", name_norm="solapur", state_code="MH",
                             district_name="Solapur", geom=from_shape(box(75.0, 17.0, 76.5, 18.5), srid=4326))
        s.add(district)
        s.flush()
        taluka = AdminArea(level="subdistrict", name="Mohol", name_norm="mohol", state_code="MH", parent_id=district.id,
                           district_name="Solapur", geom=from_shape(box(75.4, 17.6, 76.0, 18.0), srid=4326))
        s.add(taluka)
        s.flush()
        for metric, value in (("spi_18p", -2.7), ("spi_6p", -1.3), ("pop_stressed", 210000), ("pop_stressed_urban", 30000)):
            s.add(AreaIndicator(area_id=taluka.id, period=PERIOD, source="chirps-spi", metric=metric, value=value))
        s.add(AreaIndicator(area_id=taluka.id, period=PERIOD, source="gdo-soil", metric="soil_anomaly", value=-1.6))
        s.add(DroughtDeclaration(area_id=taluka.id, state_code="MH", declared_on=PERIOD, severity="severe",
                                 order_ref="GR 25 Sep 2026", source_url="https://gr.maharashtra.gov.in/x"))
        zone = Zone(name="Mohol taluka, Solapur", hazard="drought", zone_type="taluka", status="active", score=72,
                    area_id=taluka.id, district_id=district.id, population_est=210000, population_urban=30000,
                    population_source="worldpop_dry_areas", geom=taluka.geom, centroid=from_shape(Point(75.7, 17.8), srid=4326))
        s.add(zone)
        s.commit()
        ids = (str(zone.id), taluka.id, district.id)
    yield ids
    with SessionLocal() as s:
        s.query(Zone).filter(Zone.id == ids[0]).delete()
        s.query(AreaIndicator).filter(AreaIndicator.area_id == ids[1]).delete()
        s.query(DroughtDeclaration).filter(DroughtDeclaration.area_id == ids[1]).delete()
        s.query(AdminArea).filter(AdminArea.id.in_([ids[1], ids[2]])).delete(synchronize_session=False)
        s.commit()


def test_zone_page_explains_the_drought_with_measured_data(drought_zone):
    zone_id, _, _ = drought_zone
    with TestClient(app) as c:
        d = c.get(f"/api/v1/zones/{zone_id}").json()
    panel = d["drought"]
    assert panel["level"] == "severe" and panel["label"].startswith("Indicative drought footprint")
    assert panel["spi_18p"] == -2.7 and panel["soil_anomaly"] == -1.6
    assert panel["people_in_dry_areas"] == 210000 and panel["people_in_dry_areas_urban"] == 30000
    assert panel["declared"]["severity"] == "severe" and panel["declared"]["order_ref"] == "GR 25 Sep 2026"
    assert len(panel["reasons"]) >= 2
    assert d["score_breakdown"]["indicator_boost"] == 0.6 and d["score_breakdown"]["rule_met"] is True


def test_map_footprint_lists_flagged_talukas(drought_zone):
    _, taluka_id, _ = drought_zone
    with TestClient(app) as c:
        fc = c.get("/api/v1/map/footprint", params={"hazard": "drought"}).json()
        assert c.get("/api/v1/map/footprint", params={"hazard": "flood"}).status_code == 422
    mohol = next(f for f in fc["features"] if f["properties"]["id"] == taluka_id)
    assert mohol["properties"]["level"] == "severe" and mohol["properties"]["declared"] is True
    assert mohol["properties"]["district"] == "Solapur" and mohol["geometry"]["type"] in ("Polygon", "MultiPolygon")


def test_ops_shows_how_fresh_the_drought_data_is(drought_zone):
    with TestClient(app) as c:
        ops = c.get("/api/v1/ops/summary").json()
    sources = {i["source"]: i for i in ops["indicators"]}
    assert sources["chirps-spi"]["period"] == PERIOD.isoformat() and sources["chirps-spi"]["areas"] >= 1
