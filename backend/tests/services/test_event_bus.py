import uuid

from app.domain.events import SignalClassified, ZoneEscalated
from app.services.event_bus import EventBus


def test_dispatches_by_event_type_and_isolates_failing_handlers():
    bus, seen = EventBus(), []
    zone_event = ZoneEscalated(uuid.uuid4(), "drought", "Mahadevapura", 80.0, "new", "active")

    def broken(_event):
        raise RuntimeError("subscriber down")

    bus.subscribe(ZoneEscalated, broken)
    bus.subscribe(ZoneEscalated, lambda e: seen.append(("zone", e.name)))
    bus.subscribe(SignalClassified, lambda e: seen.append(("signal", e.signal_id)))
    delivered = bus.dispatch([zone_event])
    assert seen == [("zone", "Mahadevapura")]  # the broken handler did not stop the next one
    assert delivered == 1


def test_events_without_subscribers_are_ignored():
    assert EventBus().dispatch([SignalClassified(uuid.uuid4())]) == 0
