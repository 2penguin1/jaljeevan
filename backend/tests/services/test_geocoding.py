from geoalchemy2.shape import from_shape
from shapely.geometry import Point, Polygon
from sqlalchemy import select

from app.domain.geo import LocationQuery, haversine_km
from app.models import AdminArea, GeocodeCache, Signal, SignalLocation
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.geocode_cache_repository import GeocodeCacheRepository
from app.repositories.signal_repository import SignalRepository
from app.services.geocoding.geocoding_service import GeocodingService
from app.services.geocoding.resolvers import GazetteerResolver, LocatorResolver, ResolverChain


def area(db, level, name, sc, geom, pop=None, district=None):
    a = AdminArea(level=level, name=name, name_norm=name.lower(), state_code=sc, population=pop,
                  district_name=district, geom=from_shape(geom, srid=4326))
    db.add(a)
    db.flush()
    return a


def seed(db):
    area(db, "district", "Barmer", "RJ", Polygon([(70, 24), (72, 24), (72, 26.5), (70, 26.5)]), district="Barmer")
    area(db, "town", "Barmer", "RJ", Point(71.39, 25.75), pop=100000, district="Barmer")
    area(db, "town", "Aurangabad", "MH", Point(75.34, 19.88), pop=1_175_000, district="Aurangabad")
    area(db, "town", "Aurangabad", "BR", Point(84.37, 24.75), pop=102_000, district="Aurangabad")
    area(db, "village", "Rampur", "RJ", Point(71.10, 25.60), district="Barmer")
    area(db, "village", "Rampur", "UP", Point(79.02, 28.80), district="Rampur")
    area(db, "ward", "Mahadevapura", "KA", Point(77.69, 12.99), district="Bangalore Urban")


class FakeLocator:
    def __init__(self, point):
        self.point, self.calls = point, 0

    def geocode(self, query):
        self.calls += 1
        return [self.point]


def gazetteer(db) -> GazetteerResolver:
    return GazetteerResolver(AdminAreaRepository(db))


def q(mention, state=None, district=None, precision="town", near=None) -> LocationQuery:
    return LocationQuery(mention, state, district, precision, near)


def test_haversine():
    assert 1060 < haversine_km((72.88, 19.08), (77.21, 28.61)) < 1200  # Mumbai -> Delhi


def test_state_hint_disambiguates(db):
    seed(db)
    r = gazetteer(db).resolve(q("Aurangabad", "Bihar"))
    assert abs(r.lon - 84.37) < 1e-6 and r.confidence >= 0.9 and not r.ambiguous


def test_no_hint_far_candidates_is_ambiguous(db):
    seed(db)
    r = gazetteer(db).resolve(q("Aurangabad"))
    assert r.ambiguous and r.lon is None and r.precision == "state"


def test_sibling_proximity_picks_nearest(db):
    seed(db)
    r = gazetteer(db).resolve(q("Rampur village", precision="village", near=(71.39, 25.75)))
    assert abs(r.lon - 71.10) < 1e-6 and r.confidence == 0.6


def test_district_precision_uses_polygon_point(db):
    seed(db)
    r = gazetteer(db).resolve(q("Barmer district", "Rajasthan", precision="district"))
    assert r.precision == "district" and 70 < r.lon < 72


def test_unknown_name_returns_none_so_chain_continues(db):
    seed(db)
    assert gazetteer(db).resolve(q("Xyzpur", "Rajasthan", precision="village")) is None


def test_locator_fallback_checked_against_state_and_cached(db):
    seed(db)
    loc = FakeLocator((71.0, 25.0))  # inside Barmer, Rajasthan
    resolver = LocatorResolver(loc, GeocodeCacheRepository(db), AdminAreaRepository(db))
    r = resolver.resolve(q("Xyzpur", "Rajasthan", "Barmer", "village"))
    assert r.confidence == 0.6 and r.precision == "village"
    resolver.resolve(q("Xyzpur", "Rajasthan", "Barmer", "village"))
    assert loc.calls == 1 and db.scalar(select(GeocodeCache.query))
    outside = LocatorResolver(FakeLocator((88.0, 22.5)), GeocodeCacheRepository(db), AdminAreaRepository(db))
    assert outside.resolve(q("Abcpur", "Rajasthan", precision="village")) is None  # Kolkata is not in Rajasthan


def test_broad_mentions_are_skipped_by_the_chain(db):
    seed(db)
    chain = ResolverChain([gazetteer(db)])
    assert chain.resolve(q("India", precision="country")) is None
    assert chain.resolve(q("Rajasthan", precision="state")) is None


def test_geocoding_service_two_passes_and_idempotency(db):
    seed(db)
    s = Signal(source="rss", url="https://g.test/1", title="t", text="x", content_hash="g1", simhash=0,
               meta={"locations": [
                   {"mention": "India", "state_hint": None, "district_hint": None, "precision": "country"},
                   {"mention": "Barmer", "state_hint": "Rajasthan", "district_hint": None, "precision": "town"},
                   {"mention": "Rampur", "state_hint": None, "district_hint": None, "precision": "village"},
                   {"mention": "Mahadevapura", "state_hint": "Karnataka", "district_hint": "Bangalore Urban",
                    "precision": "ward"}]})
    db.add(s)
    db.flush()
    service = GeocodingService(ResolverChain([gazetteer(db)]), SignalRepository(db))
    assert service.geocode(s) == 3
    assert service.geocode(s) == 3  # idempotent: old rows replaced
    rows = db.scalars(select(SignalLocation).where(SignalLocation.signal_id == s.id)).all()
    assert len(rows) == 3
    rampur = next(r for r in rows if r.mention_text == "Rampur")
    assert rampur.geo_confidence == 0.6 and not rampur.ambiguous      # settled by proximity to Barmer
    ward = next(r for r in rows if r.mention_text == "Mahadevapura")
    assert ward.precision == "ward" and ward.geo_confidence == 0.95


def test_unresolvable_ambiguity_is_stored_without_geometry(db):
    seed(db)
    s = Signal(source="rss", url="https://g.test/2", title="t", text="x", content_hash="g2", simhash=0,
               meta={"locations": [{"mention": "Aurangabad", "state_hint": None, "district_hint": None,
                                    "precision": "town"}]})
    db.add(s)
    db.flush()
    GeocodingService(ResolverChain([gazetteer(db)]), SignalRepository(db)).geocode(s)
    row = db.scalar(select(SignalLocation).where(SignalLocation.signal_id == s.id))
    assert row.ambiguous and row.geom is None and row.precision == "state"


def test_district_precision_falls_back_to_a_taluka_but_prefers_a_real_district(db):
    seed(db)
    mohol = area(db, "subdistrict", "Mohol", "MH", Polygon([(75.4, 17.6), (76.0, 17.6), (76.0, 18.0), (75.4, 18.0)]),
                 district="Solapur")
    area(db, "subdistrict", "Barmer", "RJ", Polygon([(70.5, 25), (71.5, 25), (71.5, 26), (70.5, 26)]), district="Barmer")
    resolver = GazetteerResolver(AdminAreaRepository(db))
    r = resolver.resolve(LocationQuery("Mohol taluka", "Maharashtra", "Solapur", "district"))
    assert r.admin_area_id == mohol.id and r.precision == "subdistrict"
    barmer = resolver.resolve(LocationQuery("Barmer", "Rajasthan", None, "district"))
    assert barmer.precision == "district"  # a district and a taluka share the name: the district wins
