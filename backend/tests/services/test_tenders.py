import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, box

from app.core.exceptions import ConflictError
from app.models import Organization, User, Zone
from app.repositories.tender_repository import TenderRepository
from app.services.tender_service import TenderService

ZONE_AT = (76.21, 17.53)  # lon, lat (Akkalkot)


@pytest.fixture
def setup(db):
    gov = Organization(kind="government", name="Relief & Rehabilitation, Maharashtra", state_code="MH")
    db.add(gov)
    db.flush()
    db.add(User(email="officer@demo.test", password_hash="!", name="Demo officer", role="gov_admin", org_id=gov.id))
    vendors = []
    for name, lon, lat, tankers, price, rel in (("Near Cheap Tankers", 76.20, 17.60, 12, 55, 0.9),
                                                 ("Near Pricey Tankers", 76.30, 17.50, 8, 80, 0.95),
                                                 ("Far Away Tankers", 73.0, 19.0, 40, 50, 0.9)):
        v = Organization(kind="vendor", name=name, state_code="MH", tanker_count=tankers, tanker_capacity_kl=10,
                         base_price_per_kl=price, reliability=rel, geom=from_shape(Point(lon, lat), srid=4326))
        db.add(v)
        vendors.append(v)
    zone = Zone(name="Akkalkot taluka, Solapur", hazard="drought", zone_type="taluka", status="active", score=79,
                population_est=381611, population_urban=81621,
                geom=from_shape(box(76.0, 17.3, 76.4, 17.7), srid=4326), centroid=from_shape(Point(*ZONE_AT), srid=4326))
    db.add(zone)
    db.flush()
    return TenderService(TenderRepository(db)), zone


def test_relief_need_comes_from_the_zone_population(setup):
    service, zone = setup
    need = service.relief_need(zone.id, share=0.1)
    assert need.kl_per_day == 600.0 and need.tanker_trips_per_day == 60


def test_publishing_a_tender_invites_vendors_in_reach_with_an_opening_offer(setup):
    service, zone = setup
    tender_id = service.create(zone.id, qty_per_day=600, duration_days=30, price_per_unit=60, radius_km=100)
    detail = service.detail(tender_id)
    assert detail["status"] == "published" and detail["zone_name"] == "Akkalkot taluka, Solapur"
    names = [b["vendor_name"] for b in detail["bids"]]
    assert names == ["Near Cheap Tankers", "Near Pricey Tankers"]          # the far vendor is out of reach
    first = detail["bids"][0]
    assert first["status"] == "invited" and first["turn"] == "vendor" and "km by road" in first["reason"]
    assert first["offer"]["price_per_unit"] == 60 and first["offer"]["qty_per_day"] == 120  # 12 tankers x 10 kL
    assert detail["committed_kl_per_day"] == 0
    assert any("Invited" in m["body"] for m in first["messages"])


def test_a_counter_then_accept_commits_the_agreed_quantity(setup):
    service, zone = setup
    tender_id = service.create(zone.id, qty_per_day=600, duration_days=30, price_per_unit=60, radius_km=100)
    bid = service.detail(tender_id)["bids"][0]
    service.act(tender_id, bid["id"], side="vendor", action="counter", price_per_unit=64, qty_per_day=100,
                note="diesel costs")
    after = service.detail(tender_id)["bids"][0]
    assert (after["status"], after["turn"], after["offer"]["price_per_unit"], after["offer"]["version"]) == \
        ("countered", "gov", 64, 2)
    service.act(tender_id, bid["id"], side="gov", action="accept")
    done = service.detail(tender_id)
    assert done["bids"][0]["status"] == "accepted" and done["committed_kl_per_day"] == 100
    with pytest.raises(ConflictError):
        service.act(tender_id, bid["id"], side="vendor", action="counter", price_per_unit=70, qty_per_day=100)


def test_acting_out_of_turn_is_refused(setup):
    service, zone = setup
    tender_id = service.create(zone.id, qty_per_day=600, duration_days=30, price_per_unit=60, radius_km=100)
    bid = service.detail(tender_id)["bids"][0]
    with pytest.raises(ConflictError):
        service.act(tender_id, bid["id"], side="gov", action="accept")  # the vendor answers first


def test_suggested_price_and_vendor_list(setup):
    service, zone = setup
    assert service.suggested_price(zone.id, radius_km=100) == 67.5
    assert {v["name"] for v in service.vendors()} >= {"Near Cheap Tankers", "Far Away Tankers"}
