"""CHIRPS v3 preliminary SPI from the Climate Hazards Center (UCSB), CC BY 4.0, no login.

SPI = how unusual rainfall has been versus 1996-2025 for that place (negative = drier than normal).
06-pentad = about the last month, 18-pentad = about the last three months. New files every 5 days, ~2 days late.
"""
import re

import httpx

from app.core.exceptions import ExternalServiceError
from app.integrations.raster import INDIA_BOUNDS, Grid, fetch_window

_FILE = re.compile(r"SPI_(\d\d)PentAccum_(\d{4})_p(\d{2})_PRELIM\.tif\b")


class ChirpsSpiSource:
    SERVICE = "chirps"

    def __init__(self, http: httpx.Client, base_url: str):
        self.http = http
        self.base_url = base_url.rstrip("/")

    def _folder(self, accum: str) -> str:
        return f"{self.base_url}/{accum}_pentad/prelim/"

    def latest(self, accum: str) -> tuple[int, int] | None:
        """(year, pentad) of the newest preliminary file, or None if the folder lists none."""
        try:
            res = self.http.get(self._folder(accum), timeout=60)
        except httpx.HTTPError as exc:
            raise ExternalServiceError(self.SERVICE, f"listing failed ({type(exc).__name__})") from None
        if res.status_code >= 400:
            raise ExternalServiceError(self.SERVICE, f"listing returned HTTP {res.status_code}")
        found = {(int(y), int(p)) for a, y, p in _FILE.findall(res.text) if a == accum}
        return max(found) if found else None

    def fetch(self, accum: str, year: int, pentad: int) -> Grid:
        url = f"{self._folder(accum)}SPI_{accum}PentAccum_{year}_p{pentad:02d}_PRELIM.tif"
        return fetch_window(self.http, url, INDIA_BOUNDS, self.SERVICE)
