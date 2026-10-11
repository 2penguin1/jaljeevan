"""IMD district rainfall departure, read from the data embedded in IMD's public rainfall map page.

There is no API: the page carries an amCharts `areas` array (761 districts, each with a title, a departure like
"-45%" and a date). This is a scrape, so it is a cross-check only and fails soft: any surprise returns [].
The "season" on this page restarts on 1 Oct (post-monsoon), so the value is "rainfall since the season began".
"""
import logging
import re
from dataclasses import dataclass
from datetime import date

import httpx

LOG = logging.getLogger(__name__)

_ENTRY = re.compile(r'\{[^{}]*?"title"\s*:\s*"(?P<title>[^"]+)"[^{}]*?"info"\s*:\s*"(?P<info>[^"]*)"[^{}]*\}', re.S)
_PERCENT = re.compile(r"^(-?\d+(?:\.\d+)?)%$")
_DATE = re.compile(r"Date\s*:\s*(\d{4}-\d{2}-\d{2})")


SEASON_STARTS = ((1, 1), (3, 1), (6, 1), (10, 1))  # IMD seasons: winter, pre-monsoon, monsoon, post-monsoon
MIN_SEASON_DAYS = 21


def season_is_mature(day: date) -> bool:
    """IMD's 'since the season began' departure is noise in a season's first weeks (10 days against a tiny
    normal reads -100%). Only use it once the current season is at least three weeks old."""
    start = max(date(day.year, m, d) for m, d in SEASON_STARTS if date(day.year, m, d) <= day)
    return (day - start).days >= MIN_SEASON_DAYS


@dataclass(frozen=True)
class ImdReading:
    district: str
    departure_pct: float
    day: date


class ImdDistrictRainfall:
    URL = "https://mausam.imd.gov.in/responsive/rainfallinformation.php?msg=C"

    def __init__(self, http: httpx.Client):
        self.http = http

    def fetch(self) -> list[ImdReading]:
        try:
            res = self.http.get(self.URL, timeout=60)
        except httpx.HTTPError as exc:
            LOG.warning("IMD page unavailable (%s)", type(exc).__name__)
            return []
        if res.status_code >= 400:
            LOG.warning("IMD page returned HTTP %s", res.status_code)
            return []
        readings = self.parse(res.text)
        if not readings:
            LOG.warning("IMD page had no readable district entries (layout changed?)")
        return readings

    @staticmethod
    def parse(html: str) -> list[ImdReading]:
        out = []
        for m in _ENTRY.finditer(html):
            pct, day = _PERCENT.match(m["info"].strip()), _DATE.search(m.group(0))
            if pct and day:
                out.append(ImdReading(m["title"].strip(), float(pct.group(1)), date.fromisoformat(day.group(1))))
        return out
