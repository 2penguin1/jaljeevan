"""Two people acting on the same bid at the same moment: exactly one wins, the other is told to reload."""
import threading
import uuid

from geoalchemy2.shape import from_shape
from shapely.geometry import Point, box

from app.core.database import SessionLocal
from app.core.exceptions import ConflictError
from app.models import Bid, BidMessage, BidOffer, Organization, Tender, User, Zone
from app.repositories.tender_repository import TenderRepository
from app.services.tender_service import TenderService


def _setup():
    tag = uuid.uuid4().hex[:8]
    with SessionLocal() as s:
        gov = Organization(kind="government", name=f"Gov {tag}", state_code="MH")
        vendor = Organization(kind="vendor", name=f"Race Tankers {tag}", state_code="MH", tanker_count=5,
                              tanker_capacity_kl=10, base_price_per_kl=60, reliability=0.9,
                              geom=from_shape(Point(76.2, 17.6), srid=4326))
        s.add_all([gov, vendor])
        s.flush()
        officer = User(email=f"o-{tag}@t.test", password_hash="!", name="Officer", role="gov_admin", org_id=gov.id)
        seller = User(email=f"v-{tag}@t.test", password_hash="!", name="Seller", role="vendor", org_id=vendor.id)
        zone = Zone(name=f"Race zone {tag}", hazard="drought", zone_type="taluka", status="active", score=70,
                    population_est=1000, geom=from_shape(box(76.1, 17.5, 76.3, 17.7), srid=4326),
                    centroid=from_shape(Point(76.2, 17.6), srid=4326))
        s.add_all([officer, seller, zone])
        s.flush()
        tender_id = TenderService(TenderRepository(s)).create(zone.id, 50, 30, 60, 50, actor=officer)
        s.commit()
        bid_id = s.query(Bid).filter_by(tender_id=tender_id, vendor_org_id=vendor.id).one().id
        return tag, tender_id, bid_id, seller.id, (gov.id, vendor.id), zone.id


def _cleanup(tender_id, users_tag, orgs, zone_id):
    with SessionLocal() as s:
        bids = [b.id for b in s.query(Bid).filter_by(tender_id=tender_id)]
        s.query(BidMessage).filter(BidMessage.bid_id.in_(bids)).delete(synchronize_session=False)
        s.query(BidOffer).filter(BidOffer.bid_id.in_(bids)).delete(synchronize_session=False)
        s.query(Bid).filter(Bid.id.in_(bids)).delete(synchronize_session=False)
        s.query(Tender).filter_by(id=tender_id).delete()
        s.query(Zone).filter_by(id=zone_id).delete()
        s.query(User).filter(User.email.like(f"%{users_tag}%")).delete(synchronize_session=False)
        s.query(Organization).filter(Organization.id.in_(orgs)).delete(synchronize_session=False)
        s.commit()


def test_accept_and_decline_at_the_same_moment_only_one_wins():
    tag, tender_id, bid_id, seller_id, orgs, zone_id = _setup()
    results: dict[str, str] = {}
    start = threading.Barrier(2)

    def act(action: str):
        with SessionLocal() as s:
            seller = s.get(User, seller_id)
            start.wait()
            try:
                TenderService(TenderRepository(s)).act(tender_id, bid_id, seller, action, expected_version=1)
                s.commit()
                results[action] = "ok"
            except ConflictError:
                s.rollback()
                results[action] = "conflict"

    try:
        threads = [threading.Thread(target=act, args=(a,)) for a in ("accept", "decline")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert sorted(results.values()) == ["conflict", "ok"]
        with SessionLocal() as s:
            bid = s.get(Bid, bid_id)
            assert bid.version == 2 and bid.status in ("accepted", "declined")
    finally:
        _cleanup(tender_id, tag, orgs, zone_id)
