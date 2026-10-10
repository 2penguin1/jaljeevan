from datetime import date

from app.integrations.ports import WeatherProvider
from app.repositories.indicator_repository import IndicatorRepository


class WeatherService:
    """Refreshes today's heat/rain indicators for every district (drives the heat and flood layers)."""

    SOURCE = "open-meteo"

    def __init__(self, indicators: IndicatorRepository, provider: WeatherProvider):
        self.indicators = indicators
        self.provider = provider

    def refresh(self, today: date) -> int:
        readings = self.provider.daily(self.indicators.district_points())
        for district_id, values in readings.items():
            self.indicators.upsert(district_id, today, self.SOURCE, **values)
        return len(readings)
