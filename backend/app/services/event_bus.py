import logging
from collections import defaultdict
from collections.abc import Callable

LOG = logging.getLogger(__name__)


class EventBus:
    """Observer: delivers domain events to subscribers. Call `dispatch` only AFTER the transaction commits,
    so no alert ever goes out for data that was rolled back. A failing subscriber never blocks the others."""

    def __init__(self):
        self._handlers: dict[type, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Callable) -> None:
        self._handlers[event_type].append(handler)

    def dispatch(self, events) -> int:
        delivered = 0
        for event in events:
            handlers = self._handlers.get(type(event), [])
            for handler in handlers:
                try:
                    handler(event)
                except Exception as exc:  # noqa: BLE001 - isolate subscribers from each other
                    LOG.warning("subscriber %s failed for %s: %r", getattr(handler, "__name__", handler),
                                type(event).__name__, exc)
            delivered += bool(handlers)
        return delivered
