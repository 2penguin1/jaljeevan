import asyncio
from collections.abc import AsyncIterable

from fastapi import APIRouter, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

router = APIRouter(prefix="/api/v1", tags=["live"])

HEARTBEAT_S = 15


@router.get("/live", response_class=EventSourceResponse)
async def live(request: Request) -> AsyncIterable[ServerSentEvent]:
    """Server-Sent Events: `signal` when a post is classified, `zone` when a zone escalates."""
    relay = request.app.state.relay
    queue = relay.subscribe()
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), HEARTBEAT_S)
            except TimeoutError:
                yield ServerSentEvent(comment="heartbeat")
                continue
            yield ServerSentEvent(data=event["data"], event=event["event"])
    finally:
        relay.unsubscribe(queue)  # runs when the browser disconnects
