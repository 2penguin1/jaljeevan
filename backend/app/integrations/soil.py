"""Copernicus Global Drought Observatory soil moisture index anomaly (smang v3.0.1), CC BY 4.0, no login.

A standardised anomaly of modelled top-soil moisture against 1995-2023 (<= -1 = drier than normal), 0.05 degrees,
every dekad (10 days). Not on AWS; NASA SMAP on Earthdata Cloud (AWS) is the AWS-hosted alternative.
"""
import re
from datetime import date, datetime

import httpx

from app.core.exceptions import ExternalServiceError
from app.integrations.raster import INDIA_BOUNDS, Grid, fetch_window

_FILE = re.compile(r"smang_m_gdo_(\d{8})_t_300_z01\.tif\b")


class GdoSoilMoistureAnomaly:
    SERVICE = "gdo-soil"

    def __init__(self, http: httpx.Client, base_url: str):
        self.http = http
        self.base_url = base_url if base_url.endswith("/") else base_url + "/"

    def latest(self) -> date | None:
        """Start date of the newest dekad file, or None."""
        try:
            res = self.http.get(self.base_url, timeout=60)
        except httpx.HTTPError as exc:
            raise ExternalServiceError(self.SERVICE, f"listing failed ({type(exc).__name__})") from None
        if res.status_code >= 400:
            raise ExternalServiceError(self.SERVICE, f"listing returned HTTP {res.status_code}")
        days = {datetime.strptime(d, "%Y%m%d").date() for d in _FILE.findall(res.text)}
        return max(days) if days else None

    def fetch(self, start: date) -> Grid:
        url = f"{self.base_url}smang_m_gdo_{start:%Y%m%d}_t_300_z01.tif"
        return fetch_window(self.http, url, INDIA_BOUNDS, self.SERVICE)
