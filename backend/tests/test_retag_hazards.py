from app.cli.retag_hazards import retag
from app.models import Signal


def test_retag_recomputes_hazards_from_stored_categories_without_the_llm(db):
    old = Signal(source="rss", url="https://retag/1", title="t", text="x", content_hash="retag1", simhash=0,
                 status="classified", relevant=True, l1_codes=["SUPPLY", "RELIEF"], hazards=["drought"])
    same = Signal(source="rss", url="https://retag/2", title="t", text="x", content_hash="retag2", simhash=0,
                  status="classified", relevant=True, l1_codes=["FLOOD"], hazards=["flood"])
    pending = Signal(source="rss", url="https://retag/3", title="t", text="x", content_hash="retag3", simhash=0,
                     status="pending", l1_codes=[], hazards=[])
    db.add_all([old, same, pending])
    db.flush()
    assert retag(db) == 1
    assert old.hazards == ["water"] and same.hazards == ["flood"] and pending.hazards == []
