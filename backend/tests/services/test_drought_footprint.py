"""Drought zones come from measured data per taluka; posts only add evidence inside flagged talukas."""
from datetime import datetime, timedelta, timezone

from geoalchemy2.shape import from_shape
from shapely.geometry import Point, box
from sqlalchemy import select

from app.domain.drought import DroughtRules
from app.domain.hazards import HazardPolicies
from app.domain.lifecycle import ZoneStateMachine
from app.domain.scoring import ScoringConfig, ZoneScorer
from app.domain.zones import ZoneTypeClassifier
from app.models import AdminArea, Signal, SignalLocation, Zone
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.area_indicator_repository import AreaIndicatorRepository
from app.repositories.declaration_repository import DeclarationRepository
from app.repositories.indicator_repository import IndicatorRepository
from app.repositories.zone_repository import ZoneRepository
from app.services.drought_assessor import DroughtAssessor
from app.services.zone_detection_service import ZoneDetectionService

NOW = datetime.now(timezone.utc)
FRESH = (NOW - timedelta(days=3)).date()


def service(db) -> ZoneDetectionService:
    config = ScoringConfig()
    drought = DroughtAssessor(AreaIndicatorRepository(db), IndicatorRepository(db), DeclarationRepository(db),
                              AdminAreaRepository(db), DroughtRules())
    return ZoneDetectionService(ZoneRepository(db), AdminAreaRepository(db), IndicatorRepository(db),
                                ZoneScorer(config), HazardPolicies.default(), ZoneStateMachine(config),
                                ZoneTypeClassifier(), drought=drought)


def geo(db):
    solapur = AdminArea(level="district", name="Solapur", name_norm="solapur", state_code="MH",
                        district_name="Solapur", geom=from_shape(box(75.0, 17.0, 76.5, 18.5), srid=4326))
    delhi = AdminArea(level="district", name="New Delhi", name_norm="new delhi", state_code="DL",
                      district_name="New Delhi", geom=from_shape(box(77.0, 28.5, 77.4, 28.8), srid=4326))
    db.add_all([solapur, delhi])
    db.flush()
    mohol = AdminArea(level="subdistrict", name="Mohol", name_norm="mohol", state_code="MH", parent_id=solapur.id,
                      district_name="Solapur", geom=from_shape(box(75.4, 17.6, 76.0, 18.0), srid=4326))
    akkalkot = AdminArea(level="subdistrict", name="Akkalkot", name_norm="akkalkot", state_code="MH",
                         parent_id=solapur.id, district_name="Solapur",
                         geom=from_shape(box(76.0, 17.2, 76.4, 17.6), srid=4326))
    db.add_all([mohol, akkalkot])
    db.flush()
    return {"solapur": solapur, "delhi": delhi, "mohol": mohol, "akkalkot": akkalkot}


def dry(db, area, spi_18p=-1.7, spi_6p=-1.2, period=FRESH):
    AreaIndicatorRepository(db).upsert_many([
        (area.id, period, "chirps-spi", "spi_18p", spi_18p), (area.id, period, "chirps-spi", "spi_6p", spi_6p),
        (area.id, period, "chirps-spi", "pop_stressed", 210_000), (area.id, period, "chirps-spi", "pop_stressed_urban", 30_000)])


def post(db, url, point, *, hazards=("drought",), precision="village", area=None, domain="thehindu.com"):
    s = Signal(source="rss", url=url, domain=domain, title="t", text="x", content_hash=url, simhash=0,
               status="classified", relevant=True, event_period="current", hazards=list(hazards),
               l1_codes=["AGRI"], max_severity=4, credibility=0.8, published_at=NOW)
    db.add(s)
    db.flush()
    db.add(SignalLocation(signal_id=s.id, mention_text="x", admin_area_id=area.id if area else None,
                          precision=precision, geo_confidence=0.95, geom=from_shape(Point(*point), srid=4326)))
    db.flush()
    return s


def zones(db, hazard="drought", live_only=True):
    q = select(Zone).where(Zone.hazard == hazard)
    if live_only:
        q = q.where(Zone.status.notin_(("dismissed", "resolved")))
    return db.scalars(q).all()


def test_a_news_article_alone_never_creates_a_drought_zone(db):
    g = geo(db)
    post(db, "https://toi/solapur", (75.9, 17.7), precision="district", area=g["solapur"],
         domain="timesofindia.indiatimes.com")
    post(db, "https://hindu/solapur", (75.9, 17.7), precision="district", area=g["solapur"])
    service(db).detect(NOW, hazards=("drought",))
    assert zones(db) == []


def test_a_dry_taluka_with_a_village_report_becomes_an_active_taluka_zone(db):
    g = geo(db)
    dry(db, g["mohol"])
    post(db, "https://hindu/mohol", (75.7, 17.8))
    service(db).detect(NOW, hazards=("drought",))
    [z] = zones(db)
    assert (z.zone_type, z.area_id, z.district_id, z.name) == ("taluka", g["mohol"].id, g["solapur"].id,
                                                               "Mohol taluka, Solapur")
    assert (z.population_est, z.population_urban, z.population_source) == (210_000, 30_000, "worldpop_dry_areas")
    assert z.status == "active" and 70 < z.score < 90


def test_city_tap_complaints_stay_water_supply_outside_dry_talukas(db):
    g = geo(db)
    post(db, "https://hindu/delhi1", (77.2, 28.6), hazards=("water",), precision="ward")
    post(db, "https://ndtv/delhi1", (77.21, 28.61), hazards=("water",), precision="ward", domain="ndtv.com")
    service(db).detect(NOW)
    assert zones(db, "drought") == [] and len(zones(db, "water")) == 1


def test_water_reports_inside_a_dry_taluka_also_count_as_drought_evidence(db):
    g = geo(db)
    dry(db, g["mohol"], spi_18p=-1.2, spi_6p=-1.1)  # moderate trigger, soil unknown -> watch on data alone
    post(db, "https://hindu/mohol-wells", (75.7, 17.8), hazards=("water",))
    service(db).detect(NOW, hazards=("drought",))
    [z] = zones(db)
    assert z.independent_sources == 1 and z.score > 20


def test_taluka_zone_identity_is_stable_across_runs(db):
    g = geo(db)
    dry(db, g["mohol"])
    first = service(db).detect(NOW, hazards=("drought",))
    second = service(db).detect(NOW + timedelta(hours=1), hazards=("drought",))
    assert first.created == 1 and second.created == 0 and second.updated >= 1 and len(zones(db)) == 1


def test_data_alone_severe_is_active_and_moderate_is_watch(db):
    g = geo(db)
    dry(db, g["mohol"], spi_18p=-1.7, spi_6p=-1.6)   # severe trigger, soil unknown -> moderate (boost 0.4)
    dry(db, g["akkalkot"], spi_18p=-1.2, spi_6p=-1.1)  # moderate trigger -> watch (boost 0.2), no posts -> no zone
    service(db).detect(NOW, hazards=("drought",))
    [z] = zones(db)
    assert z.area_id == g["mohol"].id and z.status == "watch" and z.score == 40.0


def test_an_officially_declared_taluka_gets_a_zone_even_without_data(db):
    g = geo(db)
    DeclarationRepository(db).upsert(g["akkalkot"].id, "MH", FRESH, "severe", "GR 25 Sep 2026", None)
    service(db).detect(NOW, hazards=("drought",))
    [z] = zones(db)
    assert z.area_id == g["akkalkot"].id and z.status == "active" and z.score == 60.0


def test_zone_resolves_after_the_data_clears_for_72_hours(db):
    g = geo(db)
    db.add(AdminArea(level="subdistrict", name="Spare", name_norm="spare", state_code="MH",
                     geom=from_shape(box(10, 10, 11, 11), srid=4326)))
    DeclarationRepository(db).upsert(g["mohol"].id, "MH", (NOW - timedelta(days=200)).date(), "severe", None, None)
    dry(db, g["mohol"], spi_18p=-1.8, spi_6p=-1.6)
    AreaIndicatorRepository(db).upsert_many([(g["mohol"].id, FRESH, "gdo-soil", "soil_anomaly", -1.8)])
    svc = service(db)
    svc.detect(NOW, hazards=("drought",))
    [z] = zones(db)
    assert z.status == "active"
    later = NOW + timedelta(days=4)
    dry(db, g["mohol"], spi_18p=0.4, spi_6p=0.6, period=later.date())  # rain came back
    svc.detect(later, hazards=("drought",))
    svc.detect(later + timedelta(hours=73), hazards=("drought",))
    db.refresh(z)
    assert z.status == "resolving"


def test_old_post_driven_drought_zones_are_dismissed(db):
    g = geo(db)
    legacy = Zone(name="Solapur district", hazard="drought", zone_type="district_wide", status="active", score=62,
                  district_id=g["solapur"].id, geom=g["solapur"].geom)
    db.add(legacy)
    db.flush()
    service(db).detect(NOW, hazards=("drought",))
    db.refresh(legacy)
    assert legacy.status == "dismissed"
