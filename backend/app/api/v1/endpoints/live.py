import asyncio
from collections.abc import AsyncIterable

from fastapi import APIRouter, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

router = APIRouter(prefix="/api/v1", tags=["live"])

HEARTBEAT_S = 15
POLL_S = 1.0  # how often a quiet stream checks whether the browser left
RETRY_MS = 3000  # browser reconnect delay after a drop


@router.get("/live", response_class=EventSourceResponse)
async def live(request: Request) -> AsyncIterable[ServerSentEvent]:
    """Server-Sent Events: `signal` when a post is classified, `zone` when a zone escalates."""
    relay = request.app.state.relay
    queue = relay.subscribe()
    try:
        yield ServerSentEvent(retry=RETRY_MS)  # flush headers now so the browser sees the stream open
        idle = 0.0
        while not await request.is_disconnected():
            try:
                event = await asyncio.wait_for(queue.get(), POLL_S)
            except TimeoutError:
                idle += POLL_S
                if idle >= HEARTBEAT_S:
                    idle = 0.0
                    yield ServerSentEvent(comment="heartbeat")
                continue
            idle = 0.0
            yield ServerSentEvent(data=event["data"], event=event["event"])
    finally:
        relay.unsubscribe(queue)  # runs when the browser disconnects
