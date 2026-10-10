import logging
from abc import ABC, abstractmethod

import httpx

from app.core.exceptions import ExternalServiceError
from app.domain.entities import RawItem

LOG = logging.getLogger(__name__)


class BaseSourceFetcher(ABC):
    """Template Method: fetch raw rows -> map each to a RawItem -> drop rows that cannot be mapped.

    Subclasses implement only `_fetch_raw` and `_to_item`. Transport or parsing failures surface as
    ExternalServiceError so the pipeline can isolate one broken source without hiding the failure.
    """

    name: str = "base"

    @property
    def enabled(self) -> bool:
        return True

    def fetch(self) -> list[RawItem]:
        if not self.enabled:
            return []
        try:
            rows = self._fetch_raw()
        except ExternalServiceError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalServiceError(self.name, f"fetch failed: {exc!r}") from exc
        items = [item for item in (self._to_item(r) for r in rows) if item is not None]
        LOG.info("%s: %d rows -> %d items", self.name, len(rows), len(items))
        return items

    @abstractmethod
    def _fetch_raw(self) -> list[dict]: ...

    @abstractmethod
    def _to_item(self, row: dict) -> RawItem | None: ...

    @staticmethod
    def _first(row: dict, *keys, default=None):
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                return value
        return default
