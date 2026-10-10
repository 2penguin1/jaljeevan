import dataclasses
import logging

import httpx
import trafilatura

from app.domain.entities import RawItem

LOG = logging.getLogger(__name__)


class ArticleExtractor:
    """Downloads article pages and swaps headline-only text for the main article body (best effort)."""

    MAX_CHARS = 8000

    def __init__(self, client: httpx.Client, limit: int = 40, timeout: float = 8.0):
        self.client = client
        self.limit = limit
        self.timeout = timeout

    def enrich(self, items: list[RawItem]) -> list[RawItem]:
        out = []
        for i, item in enumerate(items):
            body = self._body(item.url) if i < self.limit and item.url else ""
            out.append(dataclasses.replace(item, text=body[:self.MAX_CHARS]) if len(body) > len(item.text) else item)
        return out

    def _body(self, url: str) -> str:
        try:
            html = self.client.get(url, timeout=self.timeout, follow_redirects=True).text
        except httpx.HTTPError as exc:
            LOG.info("article fetch failed for %s: %r", url, exc)
            return ""
        return trafilatura.extract(html) or ""
