import json
import logging

import httpx

LOG = logging.getLogger(__name__)


class OpenMeteoProvider:
    """Open-Meteo forecast API (free, no key): today's max temperature, feels-like max and rainfall."""

    URL = "https://api.open-meteo.com/v1/forecast"
    BATCH = 100  # coordinates per request

    def __init__(self, client: httpx.Client):
        self.client = client

    def daily(self, points: list[tuple[int, float, float]]) -> dict[int, dict]:
        out: dict[int, dict] = {}
        for i in range(0, len(points), self.BATCH):
            chunk = points[i:i + self.BATCH]
            params = {"latitude": ",".join(f"{lat:.4f}" for _, lat, _ in chunk),
                      "longitude": ",".join(f"{lon:.4f}" for _, _, lon in chunk),
                      "daily": "temperature_2m_max,apparent_temperature_max,precipitation_sum",
                      "timezone": "Asia/Kolkata", "forecast_days": 1}
            try:
                res = self.client.get(self.URL, params=params, timeout=30)
                res.raise_for_status()
                data = json.loads(res.text)
            except (httpx.HTTPError, ValueError) as exc:
                LOG.warning("open-meteo batch %d failed: %r", i // self.BATCH, exc)
                continue
            results = data if isinstance(data, list) else [data]  # one location -> object, many -> list
            for (district_id, _, _), result in zip(chunk, results):
                daily = result.get("daily") or {}
                out[district_id] = {"tmax_c": (daily.get("temperature_2m_max") or [None])[0],
                                    "apparent_tmax_c": (daily.get("apparent_temperature_max") or [None])[0],
                                    "precip_mm_24h": (daily.get("precipitation_sum") or [None])[0]}
        return out
