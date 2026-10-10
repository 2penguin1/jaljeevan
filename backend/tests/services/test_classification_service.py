import pytest

from app.domain.classification import BatchResult, Label, LocationMention, PostResult, PromptBuilder
from app.domain.evidence import EvidenceValidator
from app.domain.taxonomy import Taxonomy
from app.integrations.ports import LLMResult
from app.models import Signal, SignalLabel
from app.repositories.signal_repository import SignalRepository
from app.services.classification_service import ClassificationService


class FakeLLM:
    def __init__(self, make):
        self.make, self.calls = make, []

    def parse(self, *, system, user, schema, model, max_tokens):
        self.calls.append({"system": system, "user": user, "model": model})
        out = self.make(user)
        if isinstance(out, Exception):
            raise out
        return out


def service(db, llm) -> ClassificationService:
    tax = Taxonomy.load()
    return ClassificationService(SignalRepository(db), llm, PromptBuilder(tax), EvidenceValidator(tax), tax,
                                 model="test-model")


def add_signal(db, text, title="") -> Signal:
    s = Signal(source="gdelt", url=f"https://t.test/{abs(hash(text))}", title=title, text=text,
               content_hash=str(abs(hash(text + title))), simhash=0)
    db.add(s)
    db.flush()
    return s


def result(pid="0", **kw) -> PostResult:
    base = dict(id=pid, relevant=True, event_period="current", event_date=None, first_hand=True,
                labels=[Label(code="SUPPLY.DRY_TAPS", severity=4, evidence="no water for 11 days")],
                locations=[LocationMention(mention="Mahadevapura", state_hint="Karnataka",
                                           district_hint="Bangalore Urban", precision="ward")],
                people_affected_hint=5000, english_summary="Taps dry for 11 days.")
    base.update(kw)
    return PostResult(**base)


def ok(*results, usage=None) -> LLMResult:
    return LLMResult(parsed=BatchResult(results=list(results)), usage=usage or {})


def test_persists_labels_hazards_and_locations(db):
    s = add_signal(db, "Residents say there has been no water for 11 days in Mahadevapura ward.")
    llm = FakeLLM(lambda u: ok(result(), usage={"input_tokens": 100, "output_tokens": 50,
                                                "cache_read_input_tokens": 80}))
    stats = service(db, llm).classify([s.id])
    db.refresh(s)
    assert stats.classified == 1 and stats.input_tokens == 100 and stats.cache_read_tokens == 80
    assert s.status == "classified" and s.relevant is True and s.event_period == "current"
    assert s.l1_codes == ["SUPPLY"] and s.hazards == ["drought"] and s.max_severity == 4
    assert s.meta["locations"][0]["mention"] == "Mahadevapura"
    assert db.get(SignalLabel, (s.id, "SUPPLY.DRY_TAPS")).evidence == "no water for 11 days"
    assert llm.calls[0]["model"] == "test-model"


def test_reclassifying_replaces_labels(db):
    s = add_signal(db, "Residents say there has been no water for 11 days in Mahadevapura ward.")
    service(db, FakeLLM(lambda u: ok(result()))).classify([s.id])
    service(db, FakeLLM(lambda u: ok(result(labels=[])))).classify([s.id])
    assert db.get(SignalLabel, (s.id, "SUPPLY.DRY_TAPS")) is None


def test_relevant_but_no_valid_labels_is_unclear(db):
    s = add_signal(db, "Water situation is being discussed by the committee today in the city.")
    bad = result(labels=[Label(code="SUPPLY.DRY_TAPS", severity=3, evidence="not in the post")])
    service(db, FakeLLM(lambda u: ok(bad))).classify([s.id])
    db.refresh(s)
    assert s.status == "unclear" and s.l1_codes == []


def test_irrelevant_post(db):
    s = add_signal(db, "The water polo team from Pune won the national championship final.")
    service(db, FakeLLM(lambda u: ok(result(relevant=False, labels=[], locations=[])))).classify([s.id])
    db.refresh(s)
    assert s.status == "classified" and s.relevant is False


def test_missing_id_refusal_and_error_mark_only_affected_posts_failed(db):
    a = add_signal(db, "Taps dry in Whitefield for a week, tanker mafia charging double now.")
    b = add_signal(db, "Village handpumps dry in Barmer, women walk three km for water daily.")
    stats = service(db, FakeLLM(lambda u: ok(result("0", labels=[])))).classify([a.id, b.id])
    db.refresh(a)
    db.refresh(b)
    assert a.status == "unclear" and b.status == "failed" and b.rejected_reason == "llm_missing"
    assert stats.failed == 1

    c = add_signal(db, "Flooded underpass in Gurugram traps cars after two hours of heavy rain.")
    service(db, FakeLLM(lambda u: LLMResult(parsed=None, usage={}, refused=True))).classify([c.id])
    db.refresh(c)
    assert c.status == "failed" and c.rejected_reason == "llm_refused"

    d = add_signal(db, "Heatstroke cases rise in Nagpur hospitals as mercury crosses 47 degrees.")
    service(db, FakeLLM(lambda u: TimeoutError("boom"))).classify([d.id])
    db.refresh(d)
    assert d.status == "failed" and d.rejected_reason == "llm_error:TimeoutError"
    with pytest.raises(TimeoutError):
        service(db, FakeLLM(lambda u: TimeoutError("boom"))).classify([d.id], raise_errors=True)


def test_short_post_unclear_without_calling_llm(db):
    s = add_signal(db, "water")
    service(db, FakeLLM(lambda u: pytest.fail("LLM must not be called"))).classify([s.id])
    db.refresh(s)
    assert s.status == "unclear" and s.rejected_reason == "too_short"


def test_batches_of_ten(db):
    ids = [add_signal(db, f"Post number {i} says there is no water in the colony today.").id for i in range(23)]
    llm = FakeLLM(lambda u: ok(*[result(str(i), labels=[]) for i in range(u.count("<post id="))]))
    service(db, llm).classify(ids)
    assert len(llm.calls) == 3
