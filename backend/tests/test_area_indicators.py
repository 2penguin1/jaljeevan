from datetime import date

from geoalchemy2.shape import from_shape
from shapely.geometry import box

from app.models import AdminArea
from app.repositories.area_indicator_repository import AreaIndicatorRepository
from app.repositories.declaration_repository import DeclarationRepository


def taluka(db, name="Mohol"):
    a = AdminArea(level="subdistrict", name=name, name_norm=name.lower(), state_code="MH", district_name="Solapur",
                  geom=from_shape(box(75.4, 17.6, 76.0, 18.0), srid=4326))
    db.add(a)
    db.flush()
    return a


def test_upsert_is_idempotent_and_latest_pivots_metrics(db):
    t = taluka(db)
    repo = AreaIndicatorRepository(db)
    old, new = date(2026, 9, 30), date(2026, 10, 5)
    repo.upsert_many([(t.id, old, "chirps-spi", "spi_18p", -1.0)])
    repo.upsert_many([(t.id, new, "chirps-spi", "spi_18p", -2.0), (t.id, new, "chirps-spi", "spi_6p", -1.2)])
    repo.upsert_many([(t.id, new, "chirps-spi", "spi_18p", -2.7)])  # re-run of the same pentad overwrites
    assert repo.latest_period("chirps-spi") == new and repo.latest_period("gdo-soil") is None
    assert repo.latest("chirps-spi") == {t.id: {"period": new, "spi_18p": -2.7, "spi_6p": -1.2}}
    assert repo.latest("chirps-spi", [999]) == {}
    assert ("chirps-spi", new, 1) in repo.freshness()


def test_declarations_are_upserted_and_listed_by_area(db):
    t = taluka(db)
    repo = DeclarationRepository(db)
    repo.upsert(t.id, "MH", date(2026, 9, 25), "moderate", "GR 25 Sep 2026", "https://gr.maharashtra.gov.in/x")
    repo.upsert(t.id, "MH", date(2026, 9, 25), "severe", "GR 25 Sep 2026", "https://gr.maharashtra.gov.in/x")
    active = repo.active(since=date(2026, 4, 1))
    assert active[t.id].severity == "severe" and active[t.id].order_ref == "GR 25 Sep 2026"
    assert repo.active(since=date(2026, 10, 1)) == {}


def test_large_upserts_are_split_under_the_postgres_parameter_limit(db):
    """India has ~6,800 talukas x 4 metrics; one INSERT that big exceeds Postgres's 65,535 parameters."""
    from datetime import timedelta
    t = taluka(db)
    start = date(2000, 1, 1)
    rows = [(t.id, start + timedelta(days=i), "chirps-spi", "spi_18p", -1.0) for i in range(14_000)]  # 70k params
    assert AreaIndicatorRepository(db).upsert_many(rows) == 14_000
    assert AreaIndicatorRepository(db).latest_period("chirps-spi") == start + timedelta(days=13_999)
