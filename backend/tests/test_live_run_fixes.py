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
    assert tax.hazards_for(["RELIEF", "SUPPLY"]) == ["drought"]
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
    limited = httpx.Response(429, headers={"x-ratelimit-reset-tokens": "1m2.5s"}, json={})
    client = GroqLLMClient("k", "openai/gpt-oss-120b",
                           http=httpx.Client(transport=httpx.MockTransport(lambda r: limited)), sleep=waits.append)
    with pytest.raises(ExternalServiceError):
        client.parse(system="s", user="u", schema=Answer, max_tokens=100)
    assert waits == [62.5, 62.5, 62.5]


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
