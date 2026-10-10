from datetime import datetime, timedelta, timezone

from app.domain.entities import RawItem
from app.domain.prefilter import Prefilter

NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)
prefilter = Prefilter.default(max_age_days=30)


def item(**kw) -> RawItem:
    base = dict(source="gdelt", url="https://n.test/1", title="Tanker shortage",
                text="Villagers in Barmer wait for water tankers.", published_at=NOW, country="IN")
    base.update(kw)
    return RawItem(**base)


def test_passes_relevant_indian_item():
    assert prefilter.check(item(), NOW) is None


def test_hindi_keyword_passes():
    assert prefilter.check(item(title="गांव में पानी नहीं", text="तीन दिन से टैंकर नहीं आया"), NOW) is None


def test_too_old_rejected():
    assert prefilter.check(item(published_at=NOW - timedelta(days=45)), NOW) == "too_old"


def test_foreign_country_without_india_mention_rejected():
    assert prefilter.check(item(country="US", text="Water tankers in Texas"), NOW) == "not_india"


def test_foreign_outlet_writing_about_india_passes():
    assert prefilter.check(item(country="GB", text="Water tankers queue in Chennai, India"), NOW) is None


def test_no_keyword_rejected():
    assert prefilter.check(item(title="Election rally", text="Leaders spoke in Jaipur"), NOW) == "no_keyword"


def test_empty_rejected():
    assert prefilter.check(item(title="", text="  "), NOW) == "empty"


def test_rules_are_pluggable():
    class NoRedditRule:
        reason = "reddit_blocked"

        def rejects(self, item, body, now):
            return item.source == "reddit"

    custom = Prefilter([NoRedditRule()])
    assert custom.check(item(source="reddit"), NOW) == "reddit_blocked"
    assert custom.check(item(), NOW) is None


def test_raw_item_is_immutable():
    import dataclasses
    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        item().title = "changed"
