from datetime import date, datetime, timezone

import numpy as np
import pytest
import rasterio
from geoalchemy2.shape import from_shape
from rasterio.transform import from_origin
from shapely.geometry import box

from app.core.exceptions import ExternalServiceError
from app.integrations.population import WorldPopGrid
from app.integrations.raster import Grid
from app.models import AdminArea
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.area_indicator_repository import AreaIndicatorRepository
from app.services.indicator_refresh_service import IndicatorRefreshService

NOW = datetime(2026, 10, 11, tzinfo=timezone.utc)
# a 1-degree grid over 70..80E, 20..10N: left half (70-75E) very dry, right half normal
SPI = np.where(np.arange(10)[None, :] < 5, -2.0, 0.3).repeat(10, axis=0).astype(float)


class FakeChirps:
    def __init__(self, latest=(2026, 55), fail=False):
        self._latest, self.fail, self.fetched = latest, fail, []

    def latest(self, accum):
        if self.fail:
            raise ExternalServiceError("chirps", "HTTP 503")
        return self._latest

    def fetch(self, accum, year, pentad):
        self.fetched.append((accum, year, pentad))
        return Grid(SPI.copy(), from_origin(70, 20, 1, 1))


class FakeSoil:
    def __init__(self, latest=date(2026, 9, 21)):
        self._latest, self.fetched = latest, []

    def latest(self):
        return self._latest

    def fetch(self, start):
        self.fetched.append(start)
        return Grid(np.full((10, 10), -1.2), from_origin(70, 20, 1, 1))


@pytest.fixture
def talukas(db):
    dry = AdminArea(level="subdistrict", name="Dryland", name_norm="dryland", state_code="MH",
                    geom=from_shape(box(71, 14, 73, 16), srid=4326))
    wet = AdminArea(level="subdistrict", name="Wetland", name_norm="wetland", state_code="MH",
                    geom=from_shape(box(77, 14, 79, 16), srid=4326))
    db.add_all([dry, wet])
    db.flush()
    return dry, wet


@pytest.fixture
def population(tmp_path):
    """100 people in every 0.1-degree pixel over the same area."""
    with rasterio.open(tmp_path / "pop.tif", "w", driver="GTiff", width=100, height=100, count=1, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(70, 20, 0.1, 0.1), nodata=-99999) as dst:
        dst.write(np.full((100, 100), 100, dtype="float32"), 1)
    return WorldPopGrid(tmp_path / "pop.tif")


def service(db, chirps, soil, population):
    return IndicatorRefreshService(AreaIndicatorRepository(db), AdminAreaRepository(db), chirps, soil, population)


def test_writes_spi_soil_and_people_in_dry_cells_per_taluka(db, talukas, population):
    dry, wet = talukas
    stats = service(db, FakeChirps(), FakeSoil(), population).refresh(NOW)
    repo = AreaIndicatorRepository(db)
    spi = repo.latest("chirps-spi")
    assert spi[dry.id]["period"] == date(2026, 10, 5)
    assert spi[dry.id]["spi_18p"] == pytest.approx(-2.0) and spi[wet.id]["spi_18p"] == pytest.approx(0.3)
    assert spi[dry.id]["pop_stressed"] == pytest.approx(400 * 100)  # 2x2 degrees = 400 pixels of 100 people
    assert spi[wet.id]["pop_stressed"] == 0
    soil = repo.latest("gdo-soil")
    assert soil[dry.id]["soil_anomaly"] == pytest.approx(-1.2) and soil[dry.id]["period"] == date(2026, 9, 30)
    assert stats["chirps-spi"]["areas"] == 2 and stats["gdo-soil"]["areas"] == 2


def test_skips_sources_whose_newest_period_is_already_stored(db, talukas, population):
    chirps, soil = FakeChirps(), FakeSoil()
    service(db, chirps, soil, population).refresh(NOW)
    chirps.fetched.clear()
    soil.fetched.clear()
    stats = service(db, chirps, soil, population).refresh(NOW)
    assert chirps.fetched == [] and soil.fetched == []
    assert stats["chirps-spi"] == {"skipped": "fresh", "period": "2026-10-05"}


def test_one_failing_source_does_not_stop_the_other(db, talukas, population):
    stats = service(db, FakeChirps(fail=True), FakeSoil(), population).refresh(NOW)
    assert "error" in stats["chirps-spi"] and stats["gdo-soil"]["areas"] == 2


def test_nothing_to_do_without_talukas(db, population):
    stats = service(db, FakeChirps(), FakeSoil(), population).refresh(NOW)
    assert stats == {"skipped": "no talukas loaded"}


class FakeImd:
    def __init__(self, readings):
        self.readings = readings

    def fetch(self):
        return self.readings


def test_imd_district_departures_are_matched_by_name_and_ambiguous_names_are_skipped(db, population):
    from app.integrations.imd import ImdReading
    from app.models import DistrictIndicator
    from app.repositories.indicator_repository import IndicatorRepository
    for name, sc in (("Solapur", "MH"), ("Aurangabad", "MH"), ("Aurangabad", "BR")):
        db.add(AdminArea(level="district", name=name, name_norm=name.lower(), state_code=sc,
                         geom=from_shape(box(70, 10, 71, 11), srid=4326)))
    db.add(AdminArea(level="subdistrict", name="T", name_norm="t", state_code="MH",
                     geom=from_shape(box(71, 14, 73, 16), srid=4326)))
    db.flush()
    day = date(2026, 9, 25)  # deep into the monsoon season, so departures are meaningful
    imd = FakeImd([ImdReading("SOLAPUR", -45.0, day), ImdReading("AURANGABAD", 12.0, day),
                   ImdReading("NOWHERE", 3.0, day)])
    svc = IndicatorRefreshService(AreaIndicatorRepository(db), AdminAreaRepository(db), FakeChirps(), FakeSoil(),
                                  population, imd=imd, indicators=IndicatorRepository(db))
    stats = svc.refresh(NOW)
    assert stats["imd"] == {"day": "2026-09-25", "matched": 1, "unmatched": 2}
    row = db.query(DistrictIndicator).filter_by(source="imd").one()
    assert row.rainfall_departure_pct == -45.0 and row.period == day
    assert svc.refresh(NOW)["imd"] == {"skipped": "fresh", "day": "2026-09-25"}
    young = IndicatorRefreshService(AreaIndicatorRepository(db), AdminAreaRepository(db), FakeChirps(), FakeSoil(),
                                    population, imd=FakeImd([ImdReading("SOLAPUR", -100.0, date(2026, 10, 10))]),
                                    indicators=IndicatorRepository(db))
    assert young.refresh(NOW)["imd"] == {"skipped": "season too young", "day": "2026-10-10"}
