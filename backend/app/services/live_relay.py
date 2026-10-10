"""Postgres NOTIFY -> in-process fan-out for the SSE endpoint.

One dedicated LISTEN connection per API process (never one per browser), running in a daemon thread. Each
browser gets a bounded asyncio.Queue; when a slow client's queue is full, its oldest event is dropped.
If the database restarts, the thread reconnects on its own.
"""
import asyncio
import json
import logging
import threading

import psycopg

LOG = logging.getLogger(__name__)

CHANNELS = {"signal_classified": "signal", "zone_escalated": "zone"}


def parse_notification(channel: str, payload: str) -> dict | None:
    """Turn a NOTIFY into an SSE-ready event, or None for anything malformed or unknown."""
    if channel == "signal_classified":
        return {"event": "signal", "data": {"id": payload}}
    if channel == "zone_escalated":
        try:
            data = json.loads(payload)
        except ValueError:
            return None
        return {"event": "zone", "data": data} if isinstance(data, dict) else None
    return None


class LiveEventRelay:
    QUEUE_SIZE = 100
    RECONNECT_S = 2.0

    def __init__(self, database_url: str):
        self.dsn = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self._subscribers: set[asyncio.Queue] = set()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.QUEUE_SIZE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._stop.clear()
        self._thread = threading.Thread(target=self._listen, name="live-relay", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _listen(self) -> None:
        while not self._stop.is_set():
            try:
                with psycopg.connect(self.dsn, autocommit=True) as conn:
                    for channel in CHANNELS:
                        conn.execute(f"LISTEN {channel}")
                    while not self._stop.is_set():
                        for note in conn.notifies(timeout=1.0):
                            event = parse_notification(note.channel, note.payload)
                            if event and self._loop:
                                self._loop.call_soon_threadsafe(self._publish, event)
            except psycopg.Error as exc:
                LOG.warning("live relay lost its database connection (%s); reconnecting", type(exc).__name__)
                self._stop.wait(self.RECONNECT_S)

    def _publish(self, event: dict) -> None:
        for queue in list(self._subscribers):
            if queue.full():
                queue.get_nowait()  # slow client: drop its oldest event, keep the newest
            queue.put_nowait(event)
