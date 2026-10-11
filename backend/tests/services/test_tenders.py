import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, box

from app.core.exceptions import ConflictError, ForbiddenError
from app.models import Organization, User, Zone
from app.repositories.tender_repository import TenderRepository
from app.services.tender_service import TenderService

ZONE_AT = (76.21, 17.53)  # lon, lat (Akkalkot)


@pytest.fixture
def setup(db):
    gov = Organization(kind="government", name="Relief & Rehabilitation, Maharashtra", state_code="MH")
    db.add(gov)
    db.flush()
    officer = User(email="officer@demo.test", password_hash="!", name="Demo officer", role="gov_admin", org_id=gov.id)
    db.add(officer)
    users = {"officer": officer}
    for key, name, lon, lat, tankers, price, rel in (("cheap", "Near Cheap Tankers", 76.20, 17.60, 12, 55, 0.9),
                                                      ("pricey", "Near Pricey Tankers", 76.30, 17.50, 8, 80, 0.95),
                                                      ("far", "Far Away Tankers", 73.0, 19.0, 40, 50, 0.9)):
        v = Organization(kind="vendor", name=name, state_code="MH", tanker_count=tankers, tanker_capacity_kl=10,
                         base_price_per_kl=price, reliability=rel, geom=from_shape(Point(lon, lat), srid=4326))
        db.add(v)
        db.flush()
        users[key] = User(email=f"{key}@demo.test", password_hash="!", name=f"{name} desk", role="vendor", org_id=v.id)
        db.add(users[key])
    users["citizen"] = User(email="c@demo.test", password_hash="!", name="Citizen", role="citizen")
    db.add(users["citizen"])
    zone = Zone(name="Akkalkot taluka, Solapur", hazard="drought", zone_type="taluka", status="active", score=79,
                population_est=381611, population_urban=81621,
                geom=from_shape(box(76.0, 17.3, 76.4, 17.7), srid=4326), centroid=from_shape(Point(*ZONE_AT), srid=4326))
    db.add(zone)
    db.flush()
    return TenderService(TenderRepository(db)), zone, users


def publish(service, zone, users):
    return service.create(zone.id, qty_per_day=600, duration_days=30, price_per_unit=60, radius_km=100,
                          actor=users["officer"])


def test_relief_need_comes_from_the_zone_population(setup):
    service, zone, _ = setup
    need = service.relief_need(zone.id, share=0.1)
    assert need.kl_per_day == 600.0 and need.tanker_trips_per_day == 60


def test_only_a_relief_officer_publishes_and_vendors_in_reach_get_an_opening_offer(setup):
    service, zone, users = setup
    with pytest.raises(ForbiddenError):
        service.create(zone.id, 600, 30, 60, 100, actor=users["cheap"])
    detail = service.detail(publish(service, zone, users), viewer=users["officer"])
    assert detail["status"] == "published" and detail["zone_name"] == "Akkalkot taluka, Solapur"
    assert [b["vendor_name"] for b in detail["bids"]] == ["Near Cheap Tankers", "Near Pricey Tankers"]
    first = detail["bids"][0]
    assert (first["status"], first["turn"], first["version"]) == ("invited", "vendor", 1)
    assert first["offer"]["price_per_unit"] == 60 and first["offer"]["qty_per_day"] == 120
    assert any("Invited" in m["body"] for m in first["messages"])


def test_the_side_comes_from_the_account_and_a_vendor_only_touches_its_own_bid(setup):
    service, zone, users = setup
    tender_id = publish(service, zone, users)
    cheap = service.detail(tender_id, viewer=users["officer"])["bids"][0]
    with pytest.raises(ForbiddenError):
        service.act(tender_id, cheap["id"], users["pricey"], "accept", expected_version=1)   # someone else's bid
    with pytest.raises(ForbiddenError):
        service.act(tender_id, cheap["id"], users["citizen"], "accept", expected_version=1)
    service.act(tender_id, cheap["id"], users["cheap"], "counter", expected_version=1, price_per_unit=64,
                qty_per_day=100, note="diesel costs")
    after = service.detail(tender_id, viewer=users["officer"])["bids"][0]
    assert (after["status"], after["turn"], after["offer"]["price_per_unit"], after["version"]) == ("countered", "gov", 64, 2)
    service.act(tender_id, cheap["id"], users["officer"], "accept", expected_version=2)
    done = service.detail(tender_id, viewer=users["officer"])
    assert done["bids"][0]["status"] == "accepted" and done["committed_kl_per_day"] == 100


def test_a_stale_version_is_refused_instead_of_overwriting(setup):
    service, zone, users = setup
    tender_id = publish(service, zone, users)
    bid = service.detail(tender_id, viewer=users["officer"])["bids"][0]
    service.act(tender_id, bid["id"], users["cheap"], "counter", expected_version=1, price_per_unit=64, qty_per_day=100)
    with pytest.raises(ConflictError, match="changed"):
        service.act(tender_id, bid["id"], users["officer"], "accept", expected_version=1)


def test_out_of_turn_is_refused(setup):
    service, zone, users = setup
    tender_id = publish(service, zone, users)
    bid = service.detail(tender_id, viewer=users["officer"])["bids"][0]
    with pytest.raises(ConflictError):
        service.act(tender_id, bid["id"], users["officer"], "accept", expected_version=1)  # the vendor answers first


def test_messages_go_into_the_thread_without_changing_whose_turn_it_is(setup):
    service, zone, users = setup
    tender_id = publish(service, zone, users)
    bid = service.detail(tender_id, viewer=users["officer"])["bids"][0]
    service.message(tender_id, bid["id"], users["cheap"], "Can start from Monday with 9 tankers.")
    service.message(tender_id, bid["id"], users["officer"], "Monday works.")
    after = service.detail(tender_id, viewer=users["officer"])["bids"][0]
    assert after["turn"] == "vendor" and after["version"] == 1
    human = [m for m in after["messages"] if m["side"] != "system"]
    assert [(m["side"], m["author"]) for m in human] == [("vendor", "Near Cheap Tankers desk"), ("gov", "Demo officer")]
    with pytest.raises(ForbiddenError):
        service.message(tender_id, bid["id"], users["pricey"], "hello")


def test_raising_the_price_makes_a_new_offer_on_every_open_bid(setup):
    service, zone, users = setup
    tender_id = publish(service, zone, users)
    with pytest.raises(ForbiddenError):
        service.raise_price(tender_id, users["cheap"], 70)
    with pytest.raises(ConflictError):
        service.raise_price(tender_id, users["officer"], 55)  # must be higher
    service.raise_price(tender_id, users["officer"], 70)
    detail = service.detail(tender_id, viewer=users["officer"])
    assert detail["price_per_unit"] == 70
    for bid in detail["bids"]:
        assert (bid["offer"]["price_per_unit"], bid["offer"]["version"], bid["turn"]) == (70, 2, "vendor")
        assert any("raised the price" in m["body"] for m in bid["messages"])


def test_the_vendor_inbox_sorts_bids_by_whose_move_it_is(setup):
    service, zone, users = setup
    tender_id = publish(service, zone, users)
    assert [b["zone_name"] for b in service.inbox(users["cheap"])["needs_action"]] == ["Akkalkot taluka, Solapur"]
    bid = service.detail(tender_id, viewer=users["officer"])["bids"][0]
    service.act(tender_id, bid["id"], users["cheap"], "counter", expected_version=1, price_per_unit=64, qty_per_day=100)
    inbox = service.inbox(users["cheap"])
    assert (len(inbox["needs_action"]), len(inbox["waiting"]), len(inbox["closed"])) == (0, 1, 0)
    assert service.tenders()[0]["waiting_for_gov"] == 1
    with pytest.raises(ForbiddenError):
        service.inbox(users["officer"])


def test_suggested_price_and_vendor_list(setup):
    service, zone, _ = setup
    assert service.suggested_price(zone.id, radius_km=100) == 67.5
    assert {v["name"] for v in service.vendors()} >= {"Near Cheap Tankers", "Far Away Tankers"}


def test_offers_and_messages_are_only_shown_to_the_officer_and_that_bid_s_vendor(setup):
    service, zone, users = setup
    tender_id = publish(service, zone, users)
    bid = service.detail(tender_id, viewer=users["officer"])["bids"][0]
    service.message(tender_id, bid["id"], users["cheap"], "Our best rate is 58")
    public = service.detail(tender_id, viewer=None)
    assert all(b["offer"] is None and b["messages"] == [] for b in public["bids"])     # tender, vendors, status: open
    assert public["bids"][0]["vendor_name"] == "Near Cheap Tankers" and public["committed_kl_per_day"] == 0
    rival = service.detail(tender_id, viewer=users["pricey"])
    assert rival["bids"][0]["offer"] is None and rival["bids"][1]["offer"] is not None  # sees only its own
    own = service.detail(tender_id, viewer=users["cheap"])["bids"][0]
    assert own["offer"]["price_per_unit"] == 60 and any("58" in m["body"] for m in own["messages"])
    assert service.detail(tender_id, viewer=users["officer"])["bids"][1]["offer"] is not None
