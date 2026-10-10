import time
from collections.abc import Callable

import httpx

from app.core.exceptions import ExternalServiceError
from app.domain.entities import RawItem
from app.integrations.dates import parse_dt
from app.integrations.sources.base import BaseSourceFetcher


class GdeltFetcher(BaseSourceFetcher):
    """GDELT DOC 2.0 API: worldwide news index, filtered to Indian outlets and water/heat terms. Free.

    GDELT asks for at most one request every 5 seconds and enforces it loosely per IP, so 429s are
    retried with increasing waits before giving up.
    """

    name = "gdelt"
    URL = "https://api.gdeltproject.org/api/v2/doc/doc"
    QUERY = ('(drought OR "water crisis" OR "water shortage" OR "water tanker" OR "no water" '
             'OR flood OR waterlogging OR heatwave OR heatstroke) sourcecountry:india')
    BACKOFF_SECONDS = (6, 12)

    def __init__(self, client: httpx.Client, timespan: str = "1d", max_records: int = 250,
                 sleep: Callable[[float], None] = time.sleep):
        self.client = client
        self.timespan = timespan
        self.max_records = max_records
        self.sleep = sleep

    def _fetch_raw(self) -> list[dict]:
        params = {"query": self.QUERY, "mode": "artlist", "format": "json", "maxrecords": self.max_records,
                  "timespan": self.timespan, "sort": "datedesc"}
        for attempt, wait in enumerate((*self.BACKOFF_SECONDS, None)):
            res = self.client.get(self.URL, params=params, timeout=30)
            if res.status_code != 429:
                break
            if wait is None:
                raise ExternalServiceError(self.name, "HTTP 429 (rate limited) after retries")
            self.sleep(wait)
        if res.status_code >= 400:
            raise ExternalServiceError(self.name, f"HTTP {res.status_code}", retryable=res.status_code >= 500)
        return res.json().get("articles", [])  # GDELT answers plain text when unhappy -> ValueError

    def _to_item(self, row: dict) -> RawItem | None:
        if not row.get("url"):
            return None
        title = row.get("title", "")
        return RawItem(source=self.name, url=row["url"], title=title, text=title,
                       published_at=parse_dt(row.get("seendate")), domain=row.get("domain"),
                       lang=(row.get("language") or "")[:8] or None,
                       country="IN" if row.get("sourcecountry") == "India" else "XX")
