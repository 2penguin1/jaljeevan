from app.domain.entities import RawItem
from app.integrations.apify import ApifyClient
from app.integrations.dates import parse_dt
from app.integrations.sources.base import BaseSourceFetcher

SUBREDDITS = ("india", "bangalore", "delhi", "mumbai", "pune", "hyderabad", "chennai", "rajasthan")
REDDIT_TERMS = ("water shortage", "no water", "tanker")
X_QUERIES = (
    '"no water" (Bengaluru OR Delhi OR Chennai OR Hyderabad OR Pune OR Mumbai) lang:en',
    "#watercrisis India", "#Bengaluruwatercrisis", "@BWSSB water", "@DelhiJalBoard water",
    "waterlogging (Mumbai OR Delhi OR Bengaluru OR Gurugram)", "heatwave India hospital",
)


class _ApifySourceFetcher(BaseSourceFetcher):
    """Shared plumbing for sources scraped through an Apify actor. Disabled when no token is set."""

    max_items = 150

    def __init__(self, apify: ApifyClient, actor_id: str, enabled: bool = True):
        self.apify = apify
        self.actor_id = actor_id
        self._switched_on = enabled

    @property
    def enabled(self) -> bool:
        return self._switched_on and self.apify.configured

    def _fetch_raw(self) -> list[dict]:
        return self.apify.run_actor(self.actor_id, self.run_input(), max_items=self.max_items)

    def run_input(self) -> dict:  # field names verified against each actor's Input tab at smoke-test time
        raise NotImplementedError


class RedditFetcher(_ApifySourceFetcher):
    """Off by default (settings.reddit_enabled): the 'lite' actor is rate-limited by Reddit (HTTP 429)."""

    name = "reddit"
    max_items = 150  # actor refuses runs below 10 items

    def run_input(self) -> dict:
        return {"searches": [f"{t} subreddit:{s}" for s in SUBREDDITS for t in REDDIT_TERMS],
                "sort": "new", "time": "week", "maxItems": self.max_items, "skipComments": True}

    def _to_item(self, row: dict) -> RawItem | None:
        url = self._first(row, "url", "link", "permalink")
        if not url:
            return None
        return RawItem(source=self.name, url=url, title=self._first(row, "title", default=""),
                       text=self._first(row, "body", "text", "selftext", default=""),
                       published_at=parse_dt(self._first(row, "createdAt", "created_utc", "created")),
                       author=self._first(row, "username", "author"), domain="reddit.com", country="IN",
                       meta={"community": self._first(row, "communityName", "subreddit")})


class XFetcher(_ApifySourceFetcher):
    name = "x"

    def run_input(self) -> dict:
        return {"searchTerms": list(X_QUERIES), "maxItems": self.max_items, "sort": "Latest"}

    def _to_item(self, row: dict) -> RawItem | None:
        url = self._first(row, "url", "twitterUrl")
        if not url:
            return None
        author = row.get("author")
        handle = self._first(author, "userName", "username") if isinstance(author, dict) else author
        return RawItem(source=self.name, url=url, title="", text=self._first(row, "text", "fullText", default=""),
                       published_at=parse_dt(self._first(row, "createdAt", "created_at")),
                       author=handle, domain="x.com", country="IN")
