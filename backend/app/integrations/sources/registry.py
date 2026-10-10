from app.integrations.ports import SourceFetcher


class FetcherRegistry:
    """All known sources by name. The pipeline iterates `enabled()`; adding a source = registering one class."""

    def __init__(self):
        self._fetchers: dict[str, SourceFetcher] = {}

    def register(self, fetcher: SourceFetcher) -> None:
        self._fetchers[fetcher.name] = fetcher

    def get(self, name: str) -> SourceFetcher:
        return self._fetchers[name]

    def enabled(self) -> list[SourceFetcher]:
        return [f for f in self._fetchers.values() if f.enabled]
