"""Finding drought declarations in the news (GDELT) and downloading articles / official PDFs politely.

Polite means: robots.txt is obeyed (read once per site), at most one request per second per site, a fixed
User-Agent, and size caps so a huge or wrong file can never fill memory. No logins, captchas or paywalls.
"""
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.core.exceptions import ExternalServiceError
from app.integrations.dates import parse_dt


@dataclass(frozen=True)
class NewsHit:
    url: str
    domain: str
    title: str
    published_on: date


class DeclarationNewsSearch:
    """One GDELT DOC query for declaration coverage over the last 12 weeks (a drought season so far).

    `timespan=3months` silently returns nothing; `12w` works. GDELT allows about one request per 5 s and answers
    429 when pushed, so we wait and retry a few times, then give up for this run."""

    URL = "https://api.gdeltproject.org/api/v2/doc/doc"
    QUERY = ('("drought-hit" OR "drought affected" OR "declared drought" OR "drought declared") '
             '(taluks OR talukas OR mandals OR tehsils) sourcecountry:india')
    BACKOFF_SECONDS = (15, 30, 60)

    def __init__(self, client: httpx.Client, sleep: Callable[[float], None] = time.sleep, max_records: int = 75):
        self.client = client
        self.sleep = sleep
        self.max_records = max_records

    def search(self) -> list[NewsHit]:
        params = {"query": self.QUERY, "mode": "artlist", "format": "json", "maxrecords": self.max_records,
                  "timespan": "12w", "sort": "datedesc"}
        for wait in (*self.BACKOFF_SECONDS, None):
            res = self.client.get(self.URL, params=params, timeout=40)
            if res.status_code != 429:
                break
            if wait is None:
                raise ExternalServiceError("gdelt", "HTTP 429 (rate limited) after retries")
            self.sleep(wait)
        if res.status_code >= 400:
            raise ExternalServiceError("gdelt", f"HTTP {res.status_code}", retryable=res.status_code >= 500)
        try:
            rows = res.json().get("articles", [])
        except (ValueError, AttributeError) as exc:  # GDELT answers plain text when unhappy
            raise ExternalServiceError("gdelt", "unexpected answer") from exc
        hits = []
        for row in rows:
            seen = parse_dt(row.get("seendate"))
            if row.get("url") and seen is not None:
                hits.append(NewsHit(row["url"], row.get("domain") or urlsplit(row["url"]).hostname or "",
                                    row.get("title", ""), seen.date()))
        return hits


@dataclass(frozen=True)
class Fetched:
    url: str
    content_type: str
    body: bytes


class FetchBlocked(Exception):
    """The site's robots.txt asks us not to read this page."""


class FetchFailed(Exception):
    """The page could not be read (network, HTTP error, too big, not the expected kind of file)."""


class PoliteFetcher:
    def __init__(self, client: httpx.Client, user_agent: str, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep, min_interval: float = 1.0,
                 html_cap: int = 2_000_000, pdf_cap: int = 20_000_000, timeout: float = 20.0):
        self.client = client
        self.user_agent = user_agent
        self.clock = clock
        self.sleep = sleep
        self.min_interval = min_interval
        self.html_cap = html_cap
        self.pdf_cap = pdf_cap
        self.timeout = timeout
        self._robots: dict[str, RobotFileParser | None] = {}
        self._last: dict[str, float] = {}

    def get(self, url: str, expect_pdf: bool = False) -> Fetched:
        parts = urlsplit(url)
        site = f"{parts.scheme}://{parts.netloc}"
        robots = self._robots_for(site)
        if robots is not None and not robots.can_fetch(self.user_agent, url):
            raise FetchBlocked(url)
        cap = self.pdf_cap if expect_pdf else self.html_cap
        content_type, body = self._download(site, url, cap)
        if expect_pdf and not body.startswith(b"%PDF"):
            raise FetchFailed(f"{url}: not a PDF")
        return Fetched(url, content_type, body)

    def _robots_for(self, site: str) -> RobotFileParser | None:
        if site not in self._robots:
            # no robots.txt (4xx) = no rules; a server error or network failure = ask again later (RFC 9309), so the
            # FetchFailed is raised and the page is retried on the next run
            status, text = self._download(site, f"{site}/robots.txt", self.html_cap, robots=True)
            parser = None
            if status == "ok":
                parser = RobotFileParser()
                parser.parse(text.decode("utf-8", "replace").splitlines())
            self._robots[site] = parser  # None = no robots.txt: everything allowed
        return self._robots[site]

    def _download(self, site: str, url: str, cap: int, robots: bool = False) -> tuple[str, bytes]:
        wait = self.min_interval - (self.clock() - self._last.get(site, float("-inf")))
        if wait > 0:
            self.sleep(wait)
        self._last[site] = self.clock()
        try:
            with self.client.stream("GET", url, headers={"User-Agent": self.user_agent}, timeout=self.timeout,
                                    follow_redirects=True) as res:
                if robots and 400 <= res.status_code < 500:
                    return "missing", b""
                if res.status_code >= 400:
                    raise FetchFailed(f"{url}: HTTP {res.status_code}")
                chunks, size = [], 0
                for chunk in res.iter_bytes():
                    size += len(chunk)
                    if size > cap:
                        raise FetchFailed(f"{url}: larger than {cap} bytes")
                    chunks.append(chunk)
                return ("ok" if robots else res.headers.get("content-type", "")), b"".join(chunks)
        except httpx.HTTPError as exc:
            raise FetchFailed(f"{url}: {type(exc).__name__}") from exc
