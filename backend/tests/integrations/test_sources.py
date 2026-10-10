import httpx
import pytest

from app.core.exceptions import ExternalServiceError
from app.integrations.apify import ApifyClient
from app.integrations.dates import parse_dt
from app.integrations.sources.gdelt import GdeltFetcher
from app.integrations.sources.registry import FetcherRegistry
from app.integrations.sources.rss import RssFetcher
from app.integrations.sources.social import RedditFetcher, XFetcher


def client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parse_dt_formats():
    assert parse_dt("20261010T083000Z").isoformat() == "2026-10-10T08:30:00+00:00"
    assert parse_dt("Fri Oct 10 08:30:00 +0000 2026").day == 10
    assert parse_dt("2026-10-10T08:30:00.000Z").hour == 8
    assert parse_dt("Fri, 10 Oct 2026 08:30:00 GMT").minute == 30
    assert parse_dt(1791621000).year == 2026
    assert parse_dt("garbage") is None and parse_dt(None) is None


def test_gdelt_maps_articles_and_drops_rows_without_url():
    body = {"articles": [
        {"url": "https://thehindu.com/a", "title": "Tanker crisis in Barmer", "seendate": "20261010T083000Z",
         "domain": "thehindu.com", "language": "English", "sourcecountry": "India"},
        {"title": "no url here"}]}

    def handler(req):
        assert "api.gdeltproject.org" in str(req.url)
        return httpx.Response(200, json=body)

    items = GdeltFetcher(client(handler)).fetch()
    assert len(items) == 1
    assert items[0].source == "gdelt" and items[0].country == "IN" and items[0].domain == "thehindu.com"
    assert items[0].text == "Tanker crisis in Barmer"


def test_gdelt_throttle_text_raises_external_error():
    with pytest.raises(ExternalServiceError) as err:
        GdeltFetcher(client(lambda r: httpx.Response(200, text="Please limit requests"))).fetch()
    assert err.value.service == "gdelt" and err.value.retryable


def test_gdelt_retries_rate_limit_with_backoff():
    responses = iter([httpx.Response(429, text="Please limit requests"),
                      httpx.Response(200, json={"articles": [{"url": "https://x.in/a", "title": "t",
                                                              "sourcecountry": "India"}]})])
    waits = []
    fetcher = GdeltFetcher(client(lambda r: next(responses)), sleep=waits.append)
    assert len(fetcher.fetch()) == 1 and waits == [6]


def test_gdelt_gives_up_after_retries_with_short_message():
    waits = []
    fetcher = GdeltFetcher(client(lambda r: httpx.Response(429, text="slow down")), sleep=waits.append)
    with pytest.raises(ExternalServiceError) as err:
        fetcher.fetch()
    assert waits == [6, 12] and "HTTP 429" in str(err.value) and "api.gdeltproject.org" not in str(err.value)


def test_rss_parses_google_news_feed():
    xml = """<?xml version="1.0"?><rss><channel><item><title>Water crisis in Chennai - The Hindu</title>
    <link>https://news.google.com/rss/articles/abc</link><pubDate>Fri, 10 Oct 2026 08:30:00 GMT</pubDate>
    <description>&lt;a href="x"&gt;Residents queue for tankers&lt;/a&gt;</description>
    <source url="https://www.thehindu.com">The Hindu</source></item></channel></rss>"""
    items = RssFetcher(client(lambda r: httpx.Response(200, text=xml)), queries=["water crisis"]).fetch()
    assert len(items) == 1 and items[0].source == "rss" and "tankers" in items[0].text
    assert items[0].domain == "thehindu.com" and items[0].meta["query"] == "water crisis"


def test_reddit_and_x_map_tolerantly_through_apify():
    reddit = [{"url": "https://reddit.com/r/bangalore/1", "title": "No water 10 days",
               "body": "Whitefield society buying tankers", "createdAt": "2026-10-10T08:30:00.000Z",
               "username": "u1", "communityName": "r/bangalore"}]
    tweets = [{"url": "https://x.com/a/status/1", "text": "@BWSSB no water in HSR Layout",
               "createdAt": "Fri Oct 10 08:30:00 +0000 2026", "author": {"userName": "a"}}]

    def handler(req):
        assert "maxTotalChargeUsd=0.5" in str(req.url) and "token=tok" in str(req.url)
        return httpx.Response(201, json=reddit if "reddit" in str(req.url) else tweets)

    apify = ApifyClient(client(handler), token="tok", max_usd_per_run=0.5)
    r = RedditFetcher(apify, actor_id="trudax/reddit-scraper-lite").fetch()
    x = XFetcher(apify, actor_id="apidojo/tweet-scraper").fetch()
    assert r[0].source == "reddit" and r[0].country == "IN" and "tankers" in r[0].text
    assert r[0].meta["community"] == "r/bangalore"
    assert x[0].source == "x" and x[0].author == "a"


def test_apify_without_token_disables_social_sources():
    apify = ApifyClient(client(lambda r: pytest.fail("must not call Apify")), token=None, max_usd_per_run=0.5)
    fetcher = RedditFetcher(apify, actor_id="trudax/reddit-scraper-lite")
    assert fetcher.enabled is False and fetcher.fetch() == []


def test_apify_http_error_raises_external_error():
    apify = ApifyClient(client(lambda r: httpx.Response(402, json={"error": "payment"})), token="t",
                        max_usd_per_run=0.5)
    with pytest.raises(ExternalServiceError):
        XFetcher(apify, actor_id="apidojo/tweet-scraper").fetch()


def test_apify_error_never_contains_the_token():
    apify = ApifyClient(client(lambda r: httpx.Response(400, json={"error": "x"})), token="SECRET-TOKEN-123",
                        max_usd_per_run=0.5)
    with pytest.raises(ExternalServiceError) as err:
        apify.run_actor("a/b", {}, max_items=10)
    assert "SECRET-TOKEN-123" not in str(err.value) and "400" in str(err.value)


def test_reddit_can_be_switched_off_by_setting():
    apify = ApifyClient(client(lambda r: pytest.fail("must not call Apify")), token="t", max_usd_per_run=0.5)
    assert RedditFetcher(apify, actor_id="a/b", enabled=False).fetch() == []


def test_registry_lists_only_enabled_fetchers():
    apify = ApifyClient(client(lambda r: httpx.Response(200, json=[])), token=None, max_usd_per_run=0.5)
    reg = FetcherRegistry()
    reg.register(GdeltFetcher(client(lambda r: httpx.Response(200, json={"articles": []}))))
    reg.register(RedditFetcher(apify, actor_id="a/b"))
    assert [f.name for f in reg.enabled()] == ["gdelt"]
    assert reg.get("reddit").name == "reddit"
