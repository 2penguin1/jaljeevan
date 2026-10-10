import asyncio, json
from sqlalchemy import text
from app.core.config import settings
from app.core.database import SessionLocal
from app.services.live_relay import LiveEventRelay

def test_notify_reaches_every_subscriber_and_unsubscribe_cleans_up():
    async def scenario():
        relay = LiveEventRelay(settings.database_url)
        relay.start(asyncio.get_running_loop())
        try:
            a, b = relay.subscribe(), relay.subscribe()
            await asyncio.sleep(0.5)  # LISTEN is up
            with SessionLocal() as s:
                s.execute(text("SELECT pg_notify('signal_classified', 'abc-123')")); s.commit()
            ea = await asyncio.wait_for(a.get(), 5)
            eb = await asyncio.wait_for(b.get(), 5)
            assert ea == eb == {"event": "signal", "data": {"id": "abc-123"}}
            relay.unsubscribe(a)
            assert relay.subscriber_count == 1
        finally:
            relay.stop()
    asyncio.run(scenario())

def test_zone_payload_is_parsed_json():
    from app.services.live_relay import parse_notification
    assert parse_notification("zone_escalated", json.dumps({"zone_id": "z", "score": 80})) == \
        {"event": "zone", "data": {"zone_id": "z", "score": 80}}
    assert parse_notification("zone_escalated", "not json") is None



def test_live_stream_opens_immediately_and_unsubscribes_on_close():
    from types import SimpleNamespace
    from app.api.v1.endpoints.live import live

    async def scenario():
        relay = LiveEventRelay(settings.database_url)
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(relay=relay)))
        stream = live(request)
        first = await stream.__anext__()  # sent before any event: the browser sees the stream open at once
        assert first.retry and relay.subscriber_count == 1
        await stream.aclose()  # what the server does when the browser disconnects
        assert relay.subscriber_count == 0
    asyncio.run(scenario())
