import logging
from urllib.parse import quote_plus, urlparse

import feedparser
import httpx

from app.core.exceptions import ExternalServiceError
from app.domain.entities import RawItem
from app.domain.text import TextFingerprinter
from app.integrations.dates import parse_dt
from app.integrations.sources.base import BaseSourceFetcher

LOG = logging.getLogger(__name__)

DEFAULT_QUERIES = (
    "water crisis", "water shortage tanker", "drought district", "borewell dry",
    "flood waterlogging", "heatwave heatstroke", "पानी संकट", "सूखा", "टैंकर पानी",
)


class RssFetcher(BaseSourceFetcher):
    """Google News RSS search (India edition). One feed per query; a failing query is skipped."""

    name = "rss"

    def __init__(self, client: httpx.Client, queries=DEFAULT_QUERIES):
        self.client = client
        self.queries = tuple(queries)
        self.fp = TextFingerprinter()

    @staticmethod
    def feed_url(query: str) -> str:
        return (f"https://news.google.com/rss/search?q={quote_plus(query + ' when:2d')}"
                f"&hl=en-IN&gl=IN&ceid=IN:en")

    def _fetch_raw(self) -> list[dict]:
        rows, failures = [], 0
        for query in self.queries:
            try:
                res = self.client.get(self.feed_url(query), timeout=20)
                res.raise_for_status()
            except httpx.HTTPError as exc:
                failures += 1
                LOG.warning("rss query %r failed: %r", query, exc)
                continue
            rows += [{**entry, "_query": query} for entry in feedparser.parse(res.text).entries]
        if self.queries and failures == len(self.queries):
            raise ExternalServiceError(self.name, "every feed query failed")
        return rows

    def _to_item(self, row: dict) -> RawItem | None:
        if not row.get("link"):
            return None
        source = row.get("source") or {}
        domain = urlparse(source.get("href", "")).netloc.removeprefix("www.") or None
        title = self.fp.clean(row.get("title", ""))
        return RawItem(source=self.name, url=row["link"], title=title,
                       text=self.fp.clean(row.get("summary", "")) or title,
                       published_at=parse_dt(row.get("published")), domain=domain, country="IN",
                       meta={"query": row["_query"]})
