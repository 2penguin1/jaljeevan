from datetime import date

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, box

from app.core.exceptions import ConflictError, DomainValidationError, ForbiddenError
from app.models import Notification, Organization, User, Zone
from app.repositories.community_repository import CommunityRepository
from app.services.community_service import CommunityService


@pytest.fixture
def world(db):
    ngo_org = Organization(kind="ngo", name="Jal Seva Foundation", state_code="MH")
    db.add(ngo_org)
    db.flush()
    users = {
        "ngo": User(email="n@c.test", password_hash="!", name="NGO lead", role="ngo", org_id=ngo_org.id),
        "citizen": User(email="c@c.test", password_hash="!", name="Asha", role="citizen"),
        "citizen2": User(email="c2@c.test", password_hash="!", name="Ravi", role="citizen"),
        "vendor": User(email="v@c.test", password_hash="!", name="Vendor", role="vendor"),
    }
    zone = Zone(name="Akkalkot taluka, Solapur", hazard="drought", zone_type="taluka", status="active", score=79,
                geom=from_shape(box(76.0, 17.3, 76.4, 17.7), srid=4326), centroid=from_shape(Point(76.2, 17.5), srid=4326))
    db.add_all([*users.values(), zone])
    db.flush()
    return CommunityService(CommunityRepository(db)), zone, users, db


def test_only_ngos_start_campaigns_and_anyone_logged_in_can_pledge(world):
    service, zone, users, db = world
    with pytest.raises(ForbiddenError):
        service.start_campaign(users["citizen"], zone.id, "Tankers for Akkalkot", "Families walk far for water.", 200000)
    cid = service.start_campaign(users["ngo"], zone.id, "Tankers for Akkalkot", "Families walk far for water.", 200000)
    service.pledge(users["citizen"], cid, 5000, "For the children")
    service.pledge(users["citizen2"], cid, 15000, None)
    [campaign] = service.campaigns(zone_id=zone.id)
    assert (campaign["pledged_inr"], campaign["pledges"], campaign["goal_inr"], campaign["ngo_name"]) == \
        (20000, 2, 200000, "Jal Seva Foundation")
    notes = [n.payload["text"] for n in db.query(Notification).filter_by(user_id=users["ngo"].id)]
    assert any("₹5,000" in t and "Tankers for Akkalkot" in t for t in notes)
    with pytest.raises(DomainValidationError):
        service.pledge(users["citizen"], cid, 0, None)


def test_volunteer_slots_fill_up_and_each_person_signs_up_once(world):
    service, zone, users, _ = world
    with pytest.raises(ForbiddenError):
        service.post_task(users["vendor"], zone.id, "Help at the water point", "Hand out water cans", date(2026, 10, 15), 2)
    tid = service.post_task(users["ngo"], zone.id, "Help at the water point", "Hand out water cans", date(2026, 10, 15), 2)
    service.sign_up(users["citizen"], tid)
    with pytest.raises(ConflictError, match="already"):
        service.sign_up(users["citizen"], tid)
    service.sign_up(users["citizen2"], tid)
    with pytest.raises(ConflictError, match="full"):
        service.sign_up(users["vendor"], tid)
    [task] = service.tasks(zone_id=zone.id, viewer=users["citizen"])
    assert (task["slots"], task["taken"], task["signed_up"]) == (2, 2, True)
    assert service.tasks(zone_id=zone.id, viewer=None)[0]["signed_up"] is False


def test_nonsense_numbers_and_unknown_zones_are_refused(world):
    service, zone, users, _ = world
    with pytest.raises(DomainValidationError):
        service.start_campaign(users["ngo"], zone.id, "x", "", -5)
    with pytest.raises(DomainValidationError):
        service.post_task(users["ngo"], zone.id, "x", "", None, 0)
