from datetime import datetime, timedelta, timezone

from geoalchemy2.shape import from_shape
from shapely.geometry import Point, Polygon
from sqlalchemy import func, select

from app.domain.hazards import HazardPolicies
from app.domain.lifecycle import ZoneStateMachine
from app.domain.scoring import ScoringConfig, ZoneScorer
from app.domain.zones import ZoneTypeClassifier
from app.models import (AdminArea, DistrictIndicator, Signal, SignalFeedback, SignalLocation, User, Zone,
                        ZoneSignal, ZoneSnapshot)
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.indicator_repository import IndicatorRepository
from app.repositories.zone_repository import ZoneRepository
from app.services.zone_detection_service import ZoneDetectionService

NOW = datetime.now(timezone.utc)
BLR = Polygon([(77.4, 12.8), (77.8, 12.8), (77.8, 13.2), (77.4, 13.2)])
BARMER = Polygon([(70, 24), (72, 24), (72, 26.5), (70, 26.5)])


def service(db) -> ZoneDetectionService:
    config = ScoringConfig()
    return ZoneDetectionService(ZoneRepository(db), AdminAreaRepository(db), IndicatorRepository(db),
                                ZoneScorer(config), HazardPolicies.default(), ZoneStateMachine(config),
                                ZoneTypeClassifier())


def seed_geo(db):
    blr = AdminArea(level="district", name="Bangalore Urban", name_norm="bangalore urban", state_code="KA",
                    population=9_600_000, district_name="Bangalore Urban", geom=from_shape(BLR, srid=4326))
    bmr = AdminArea(level="district", name="Barmer", name_norm="barmer", state_code="RJ", population=2_600_000,
                    district_name="Barmer", geom=from_shape(BARMER, srid=4326))
    ward = AdminArea(level="ward", name="Mahadevapura", name_norm="mahadevapura", state_code="KA", is_urban=True,
                     population=60000, district_name="Bangalore Urban", geom=from_shape(Point(77.69, 12.99), srid=4326))
    vil = AdminArea(level="village", name="Dhorimanna", name_norm="dhorimanna", state_code="RJ", population=8000,
                    district_name="Barmer", geom=from_shape(Point(71.43, 25.20), srid=4326))
    db.add_all([blr, bmr, ward, vil])
    db.flush()
    return {"blr": blr, "bmr": bmr, "ward": ward, "vil": vil}


def sig(db, *, url, point, area=None, precision="ward", source="gdelt", domain="thehindu.com", cred=0.8,
        severity=4, hazards=("drought",), period="current", author=None, conf=0.95, days_old=0, **kw):
    s = Signal(source=source, url=url, domain=domain, author=author, title="t", text="x", content_hash=url,
               simhash=0, status="classified", relevant=True, event_period=period, hazards=list(hazards),
               l1_codes=["SUPPLY"], max_severity=severity, credibility=cred,
               published_at=NOW - timedelta(days=days_old), **kw)
    db.add(s)
    db.flush()
    db.add(SignalLocation(signal_id=s.id, mention_text=area.name if area else "X",
                          admin_area_id=area.id if area else None, precision=precision, geo_confidence=conf,
                          geom=from_shape(Point(*point), srid=4326) if point else None, ambiguous=point is None))
    db.flush()
    return s


def zones(db, hazard="drought"):
    return db.scalars(select(Zone).where(Zone.hazard == hazard)).all()


def test_zone_type_rules():
    c = ZoneTypeClassifier()
    assert c.classify([{"level": "ward", "is_urban": True, "precision": "ward"}]) == "urban_pocket"
    assert c.classify([{"level": "town", "is_urban": True, "precision": "town"}]) == "town"
    assert c.classify([{"level": "village", "is_urban": False, "precision": "village"}]) == "rural"


def test_two_independent_sources_make_an_active_urban_pocket_and_an_alert(db):
    g = seed_geo(db)
    sig(db, url="https://a/1", point=(77.690, 12.990), area=g["ward"])
    sig(db, url="https://b/1", point=(77.695, 12.993), area=g["ward"], domain="ndtv.com")
    result = service(db).detect(NOW, hazards=("drought",))
    [z] = zones(db)
    assert z.status == "active" and z.zone_type == "urban_pocket" and z.score >= 60
    assert z.independent_sources == 2 and z.population_est == 60000 and z.population_source == "gazetteer"
    assert "Mahadevapura" in z.name and result.created == 1
    assert [e.zone_id for e in result.events] == [z.id]  # new + score >= 70 -> ZoneEscalated
    assert db.scalar(select(func.count()).select_from(ZoneSignal)) == 2


def test_single_social_post_is_only_a_watch_marker(db):
    g = seed_geo(db)
    sig(db, url="https://r/1", point=(77.69, 12.99), area=g["ward"], source="reddit", domain="reddit.com",
        cred=0.4, author="u1")
    result = service(db).detect(NOW, hazards=("drought",))
    [z] = zones(db)
    assert z.status == "watch" and z.score < 60 and result.events == []


def test_ineligible_signals_never_form_zones(db):
    g = seed_geo(db)
    sig(db, url="https://p/1", point=(77.69, 12.99), area=g["ward"], period="past")
    sig(db, url="https://p/2", point=None, area=g["ward"], precision="state")      # ambiguous, no geometry
    sig(db, url="https://p/3", point=(77.69, 12.99), area=g["ward"], severity=2)   # too mild
    sig(db, url="https://p/4", point=(77.69, 12.99), area=g["ward"], days_old=45)  # too old
    flagged = sig(db, url="https://p/5", point=(77.69, 12.99), area=g["ward"])
    reviewer = User(email="g@x", password_hash="x", name="g", role="gov_admin")
    db.add(reviewer)
    db.flush()
    db.add(SignalFeedback(signal_id=flagged.id, user_id=reviewer.id, verdict="false"))
    db.flush()
    service(db).detect(NOW, hazards=("drought",))
    assert zones(db) == []


def test_zone_keeps_its_id_across_runs_and_snapshots_accumulate(db):
    g = seed_geo(db)
    sig(db, url="https://a/1", point=(77.690, 12.990), area=g["ward"])
    service(db).detect(NOW, hazards=("drought",))
    first = zones(db)[0].id
    sig(db, url="https://b/1", point=(77.700, 12.995), area=g["ward"], domain="ndtv.com")
    result = service(db).detect(NOW, hazards=("drought",))
    assert [z.id for z in zones(db)] == [first] and result.updated == 1 and result.created == 0
    assert db.scalar(select(func.count()).select_from(ZoneSnapshot)) == 2


def test_far_apart_points_make_separate_zones_with_correct_types(db):
    g = seed_geo(db)
    for i, d in enumerate(("thehindu.com", "ndtv.com")):
        sig(db, url=f"https://u/{i}", point=(77.69, 12.99), area=g["ward"], domain=d)
        sig(db, url=f"https://v/{i}", point=(71.43, 25.20), area=g["vil"], precision="village", domain=d)
    service(db).detect(NOW, hazards=("drought",))
    assert sorted(z.zone_type for z in zones(db)) == ["rural", "urban_pocket"]


def test_severe_indicator_alone_creates_a_district_wide_watch_zone(db):
    g = seed_geo(db)
    db.add(DistrictIndicator(district_id=g["bmr"].id, period=NOW.date(), rainfall_departure_pct=-52, source="imd"))
    db.flush()
    service(db).detect(NOW, hazards=("drought",))
    [z] = zones(db)
    assert z.zone_type == "district_wide" and z.district_id == g["bmr"].id
    assert z.score == 40.0 and z.status == "watch" and z.population_est == 2_600_000


def test_hazards_are_kept_separate(db):
    g = seed_geo(db)
    sig(db, url="https://h/1", point=(77.69, 12.99), area=g["ward"], hazards=("heat",))
    sig(db, url="https://h/2", point=(77.69, 12.99), area=g["ward"], hazards=("heat",), domain="ndtv.com")
    service(db).detect(NOW)
    assert zones(db, "drought") == [] and len(zones(db, "heat")) == 1


def test_zone_without_new_evidence_decays(db):
    g = seed_geo(db)
    sig(db, url="https://a/1", point=(77.690, 12.990), area=g["ward"])
    sig(db, url="https://b/1", point=(77.695, 12.993), area=g["ward"], domain="ndtv.com")
    service(db).detect(NOW, hazards=("drought",))
    later = NOW + timedelta(days=40)  # evidence now outside the 30-day window
    service(db).detect(later, hazards=("drought",))
    [z] = zones(db)
    assert z.score == 0.0
