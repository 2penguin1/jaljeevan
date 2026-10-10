import json
from datetime import date

import httpx
from geoalchemy2.shape import from_shape
from shapely.geometry import Polygon
from sqlalchemy import select

from app.integrations.weather import OpenMeteoProvider
from app.models import AdminArea, DistrictIndicator
from app.repositories.indicator_repository import IndicatorRepository
from app.services.weather_service import WeatherService


def test_weather_service_upserts_one_row_per_district(db):
    district = AdminArea(level="district", name="Barmer", name_norm="barmer", state_code="RJ",
                         geom=from_shape(Polygon([(71, 25), (72, 25), (72, 26), (71, 26)]), srid=4326))
    db.add(district)
    db.flush()
    payload = {"latitude": 25.5, "longitude": 71.5, "daily": {
        "time": ["2026-10-10"], "temperature_2m_max": [41.2],
        "apparent_temperature_max": [46.0], "precipitation_sum": [0.0]}}
    provider = OpenMeteoProvider(httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, text=json.dumps(payload)))))
    service = WeatherService(IndicatorRepository(db), provider)

    assert service.refresh(date(2026, 10, 10)) == 1
    assert service.refresh(date(2026, 10, 10)) == 1  # idempotent upsert
    rows = db.scalars(select(DistrictIndicator).where(DistrictIndicator.source == "open-meteo")).all()
    assert len(rows) == 1 and rows[0].apparent_tmax_c == 46.0 and rows[0].tmax_c == 41.2


def test_weather_batch_failure_is_skipped_not_fatal(db):
    db.add(AdminArea(level="district", name="X", name_norm="x", state_code="RJ",
                     geom=from_shape(Polygon([(71, 25), (72, 25), (72, 26), (71, 26)]), srid=4326)))
    db.flush()
    provider = OpenMeteoProvider(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))))
    assert WeatherService(IndicatorRepository(db), provider).refresh(date(2026, 10, 10)) == 0
