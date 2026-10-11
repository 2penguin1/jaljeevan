from datetime import date

import httpx
import pytest

from app.core.exceptions import ExternalServiceError
from app.integrations.declaration_news import DeclarationNewsSearch, FetchBlocked, FetchFailed, PoliteFetcher

ARTLIST = {"articles": [
    {"url": "https://www.siasat.com/karnataka-drought-hit-taluks-rise-to-217-after-40-added-3551196/",
     "title": "Karnataka drought - hit Taluks rise to 217 after 40 added", "seendate": "20261002T061500Z",
     "domain": "siasat.com", "language": "English", "sourcecountry": "India"},
    {"url": "", "title": "no url", "seendate": "20261002T061500Z", "domain": "x.com"},
]}


def mock(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_search_parses_hits_and_asks_for_twelve_weeks():
    seen = {}

    def handler(request):
        seen.update(request.url.params)
        return httpx.Response(200, json=ARTLIST)

    [hit] = DeclarationNewsSearch(mock(handler)).search()
    assert (hit.domain, hit.published_on) == ("siasat.com", date(2026, 10, 2))
    assert seen["timespan"] == "12w" and "taluks" in seen["query"]


def test_search_waits_out_rate_limits_then_gives_up():
    calls, waits = [], []

    def flaky(request):
        calls.append(1)
        return httpx.Response(429) if len(calls) < 3 else httpx.Response(200, json=ARTLIST)

    assert len(DeclarationNewsSearch(mock(flaky), sleep=waits.append).search()) == 1
    assert len(waits) == 2
    with pytest.raises(ExternalServiceError):
        DeclarationNewsSearch(mock(lambda r: httpx.Response(429)), sleep=lambda s: None).search()


class Clock:
    def __init__(self):
        self.now = 100.0
        self.slept: list[float] = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(round(seconds, 2))
        self.now += seconds


def fetcher(routes: dict, clock: Clock | None = None, **kw) -> tuple[PoliteFetcher, list[str]]:
    hits: list[str] = []

    def handler(request):
        hits.append(str(request.url))
        for key, response in routes.items():
            if str(request.url).endswith(key):
                return response
        return httpx.Response(404)

    clock = clock or Clock()
    return PoliteFetcher(mock(handler), "jal-test/0.1", clock=clock, sleep=clock.sleep, **kw), hits


def test_robots_txt_is_respected_and_read_once_per_site():
    f, hits = fetcher({"/robots.txt": httpx.Response(200, text="User-agent: *\nDisallow: /private/"),
                       "/news/a": httpx.Response(200, text="<p>ok</p>", headers={"content-type": "text/html"})})
    assert f.get("https://site.test/news/a").body == b"<p>ok</p>"
    with pytest.raises(FetchBlocked):
        f.get("https://site.test/private/b")
    assert sum(h.endswith("/robots.txt") for h in hits) == 1


def test_a_missing_robots_txt_allows_fetching():
    f, _ = fetcher({"/a": httpx.Response(200, text="hi")})
    assert f.get("https://open.test/a").body == b"hi"


def test_at_most_one_request_per_second_per_site():
    clock = Clock()
    f, _ = fetcher({"/a": httpx.Response(200, text="a"), "/b": httpx.Response(200, text="b")}, clock)
    f.get("https://one.test/a")      # robots.txt, then the page a second later (robots.txt is a request too)
    clock.now += 0.2
    f.get("https://one.test/b")
    assert clock.slept == [1.0, 0.8]
    clock.now += 5
    f.get("https://two.test/a")      # another site is not slowed by the first one
    assert clock.slept == [1.0, 0.8, 1.0]


def test_oversized_bodies_fake_pdfs_and_server_errors_fail():
    f, _ = fetcher({"/big": httpx.Response(200, content=b"x" * 50), "/order.pdf": httpx.Response(200, text="<html>"),
                    "/err": httpx.Response(500)}, html_cap=10)
    with pytest.raises(FetchFailed):
        f.get("https://s.test/big")
    with pytest.raises(FetchFailed):
        f.get("https://s.test/order.pdf", expect_pdf=True)
    with pytest.raises(FetchFailed):
        f.get("https://s.test/err")


def test_a_real_pdf_is_returned():
    f, _ = fetcher({"/order.pdf": httpx.Response(200, content=b"%PDF-1.7 data")})
    assert f.get("https://revenue.kar.nic.in/order.pdf", expect_pdf=True).body.startswith(b"%PDF")


def test_a_robots_txt_server_error_means_try_later():
    f, _ = fetcher({"/robots.txt": httpx.Response(503), "/a": httpx.Response(200, text="hi")})
    with pytest.raises(FetchFailed):
        f.get("https://down.test/a")
