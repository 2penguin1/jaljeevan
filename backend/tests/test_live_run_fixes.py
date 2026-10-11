"""Regression tests for bugs found in the first live pipeline run (each failed before its fix)."""
import httpx
import pytest
from pydantic import BaseModel

from app.core.exceptions import ExternalServiceError
from app.domain.taxonomy import Taxonomy
from app.integrations.groq import GroqLLMClient
from app.models import Signal
from app.repositories.signal_repository import SignalRepository


class Answer(BaseModel):
    label: str


# Bug B: generic categories must not decide the hazard
def test_generic_categories_do_not_assign_every_hazard():
    tax = Taxonomy.load()
    assert tax.hazards_for(["RELIEF", "SUPPLY"]) == ["water"]
    assert tax.hazards_for(["RELIEF"]) == []                       # generic only -> no hazard -> no zone
    assert tax.hazards_for(["HEALTH", "FLOOD", "HEAT"]) == ["flood", "heat"]


# Bug A: Groq rate limits are waited out, and gpt-oss reasons briefly
def ok_response():
    return httpx.Response(200, json={"choices": [{"message": {"content": '{"label": "x"}'}}], "usage": {}})


def test_groq_waits_out_rate_limit_then_succeeds():
    responses = iter([httpx.Response(429, headers={"retry-after": "7"}, json={}), ok_response()])
    waits, bodies = [], []

    def handler(req):
        bodies.append(req.content)
        return next(responses)

    client = GroqLLMClient("k", "openai/gpt-oss-120b", http=httpx.Client(transport=httpx.MockTransport(handler)),
                           sleep=waits.append)
    result = client.parse(system="s", user="u", schema=Answer, max_tokens=100)
    assert result.parsed == Answer(label="x") and waits == [7.0]
    assert b'"reasoning_effort":"low"' in bodies[0].replace(b" ", b"")


def test_groq_uses_token_reset_header_and_gives_up_after_retries():
    waits = []
    limited = httpx.Response(429, headers={"x-ratelimit-reset-tokens": "45.5s"}, json={})  # under the 60 s cap
    client = GroqLLMClient("k", "openai/gpt-oss-120b",
                           http=httpx.Client(transport=httpx.MockTransport(lambda r: limited)), sleep=waits.append)
    with pytest.raises(ExternalServiceError):
        client.parse(system="s", user="u", schema=Answer, max_tokens=100)
    assert waits == [45.5, 45.5, 45.5]


# Retry: posts that failed on a temporary LLM error are queued again; refusals are not
def test_transient_llm_failures_are_requeued_but_refusals_are_not(db):
    rows = [Signal(source="rss", url=f"https://q/{i}", title="t", text="x", content_hash=f"q{i}", simhash=0,
                   status=status, rejected_reason=reason)
            for i, (status, reason) in enumerate([("pending", None), ("failed", "llm_error:ExternalServiceError"),
                                                  ("failed", "llm_refused"), ("failed", "llm_missing")])]
    db.add_all(rows)
    db.flush()
    queued = set(SignalRepository(db).pending_ids(limit=10))
    assert queued == {rows[0].id, rows[1].id, rows[3].id}


# Bug C: one off-list word from the model must not invalidate a whole batch
def test_model_synonyms_are_coerced_not_rejected():
    from app.domain.classification import LocationMention, PostResult
    assert LocationMention(mention="Hyderabad", state_hint=None, district_hint=None, precision="city").precision == "town"
    assert LocationMention(mention="Adyar", state_hint=None, district_hint=None, precision="Neighbourhood").precision == "ward"
    assert LocationMention(mention="X", state_hint=None, district_hint=None, precision="galaxy").precision == "unknown"
    post = PostResult(id="0", relevant=True, event_period="ongoing", event_date=None, first_hand=False, labels=[],
                      locations=[], people_affected_hint=None, english_summary="x")
    assert post.event_period == "current"


def test_groq_requests_strict_schema_without_extra_fields():
    import json as _json
    from app.domain.classification import BatchResult
    seen = {}

    def handler(req):
        seen["body"] = _json.loads(req.content)
        return ok_response()

    client = GroqLLMClient("k", "openai/gpt-oss-120b", http=httpx.Client(transport=httpx.MockTransport(handler)),
                           sleep=lambda s: None)
    client.parse(system="s", user="u", schema=BatchResult, max_tokens=100)
    spec = seen["body"]["response_format"]["json_schema"]
    assert spec["strict"] is True

    def objects(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                yield node
            for v in node.values():
                yield from objects(v)
        elif isinstance(node, list):
            for v in node:
                yield from objects(v)

    found = list(objects(spec["schema"]))
    assert found and all(o.get("additionalProperties") is False for o in found)
