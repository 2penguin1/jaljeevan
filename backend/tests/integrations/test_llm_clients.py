import json

import httpx
import pytest
from pydantic import BaseModel

from app.core.exceptions import ExternalServiceError
from app.integrations.bedrock import BedrockLLMClient
from app.integrations.fallback import FallbackLLMClient
from app.integrations.groq import GroqLLMClient
from app.integrations.ports import LLMResult


class Answer(BaseModel):
    label: str
    score: int


def groq(handler) -> GroqLLMClient:
    return GroqLLMClient("gsk-test", model="openai/gpt-oss-120b",
                         http=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None)


def chat_response(content: str, **message) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content, **message}}],
                                     "usage": {"prompt_tokens": 12, "completion_tokens": 5}})


# -- Groq adapter ------------------------------------------------------------------------------
def test_groq_sends_openai_style_request_with_json_schema():
    seen = {}

    def handler(req):
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], json.loads(req.content)
        return chat_response('{"label": "SUPPLY", "score": 4}')

    result = groq(handler).parse(system="sys", user="usr", schema=Answer, max_tokens=500)
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions" and seen["auth"] == "Bearer gsk-test"
    body = seen["body"]
    assert body["model"] == "openai/gpt-oss-120b" and body["max_completion_tokens"] == 500
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"]["properties"].keys() == {"label", "score"}
    assert result.parsed == Answer(label="SUPPLY", score=4)
    assert result.provider == "groq:openai/gpt-oss-120b"
    assert result.usage == {"input_tokens": 12, "output_tokens": 5, "cache_read_input_tokens": 0}


def test_groq_invalid_json_is_not_an_outage():
    result = groq(lambda r: chat_response("not json at all")).parse(system="s", user="u", schema=Answer, max_tokens=50)
    assert result.parsed is None and not result.refused


def test_groq_refusal_is_reported():
    result = groq(lambda r: chat_response("", refusal="I can't help with that")).parse(
        system="s", user="u", schema=Answer, max_tokens=50)
    assert result.refused and result.parsed is None


def test_groq_rate_limit_is_a_retryable_external_error_without_the_key():
    with pytest.raises(ExternalServiceError) as err:
        groq(lambda r: httpx.Response(429, json={"error": "slow"})).parse(system="s", user="u", schema=Answer,
                                                                          max_tokens=50)
    assert err.value.retryable and "429" in str(err.value) and "gsk-test" not in str(err.value)


# -- Bedrock adapter: vendor errors become ExternalServiceError ---------------------------------
def test_bedrock_access_errors_are_normalised():
    import anthropic

    def boom(**kw):
        raise anthropic.NotFoundError("Model use case details have not been submitted",
                                      response=httpx.Response(404, request=httpx.Request("POST", "http://x")),
                                      body=None)

    class Boom:
        class messages:
            create = staticmethod(boom)  # Haiku 4.5 path (forced tool call)
            parse = staticmethod(boom)   # newer-model path (structured output)

    client = BedrockLLMClient("ap-south-1", model="in.anthropic.claude-haiku-4-5-20251001-v1:0", client=Boom())
    with pytest.raises(ExternalServiceError) as err:
        client.parse(system="s", user="u", schema=Answer, max_tokens=50)
    assert err.value.service == "bedrock" and "404" in str(err.value)


def test_bedrock_haiku_45_uses_forced_tool_call_for_structured_output():
    calls = {}

    class Block:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class Fake:
        class messages:
            @staticmethod
            def create(**kw):
                calls.update(kw)
                usage = Block(input_tokens=30, output_tokens=8, cache_read_input_tokens=20)
                content = [Block(type="tool_use", name="submit_result", input={"label": "SUPPLY", "score": 3})]
                return Block(content=content, usage=usage, stop_reason="tool_use")

            @staticmethod
            def parse(**kw):
                raise AssertionError("structured-output API must not be used for Haiku 4.5 on Bedrock")

    client = BedrockLLMClient("ap-south-1", model="in.anthropic.claude-haiku-4-5-20251001-v1:0", client=Fake())
    result = client.parse(system="sys", user="usr", schema=Answer, max_tokens=100)
    assert calls["tool_choice"] == {"type": "tool", "name": "submit_result"}
    assert calls["tools"][0]["input_schema"]["properties"].keys() == {"label", "score"}
    assert calls["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert result.parsed == Answer(label="SUPPLY", score=3) and result.usage["cache_read_input_tokens"] == 20


def test_bedrock_tool_answer_that_fails_schema_is_invalid_not_outage():
    class Block:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class Fake:
        class messages:
            @staticmethod
            def create(**kw):
                return Block(content=[Block(type="tool_use", name="submit_result", input={"label": 5})],
                             usage=Block(input_tokens=1, output_tokens=1), stop_reason="tool_use")

    result = BedrockLLMClient("r", model="in.anthropic.claude-haiku-4-5-20251001-v1:0", client=Fake()).parse(
        system="s", user="u", schema=Answer, max_tokens=10)
    assert result.parsed is None and not result.refused


# -- Fallback chain -----------------------------------------------------------------------------
class Stub:
    def __init__(self, name, outcome):
        self.name, self.outcome, self.calls = name, outcome, 0

    def parse(self, **kw):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def test_fallback_uses_next_provider_on_outage():
    primary = Stub("bedrock", ExternalServiceError("bedrock", "HTTP 404"))
    backup = Stub("groq", LLMResult(parsed=Answer(label="x", score=1), provider="groq:m"))
    result = FallbackLLMClient([primary, backup]).parse(system="s", user="u", schema=Answer, max_tokens=10)
    assert result.provider == "groq:m" and primary.calls == backup.calls == 1


def test_fallback_does_not_bypass_a_refusal():
    primary = Stub("bedrock", LLMResult(parsed=None, refused=True, provider="bedrock:m"))
    backup = Stub("groq", LLMResult(parsed=Answer(label="x", score=1), provider="groq:m"))
    result = FallbackLLMClient([primary, backup]).parse(system="s", user="u", schema=Answer, max_tokens=10)
    assert result.refused and backup.calls == 0


def test_fallback_raises_when_every_provider_is_down():
    chain = FallbackLLMClient([Stub("a", ExternalServiceError("a", "down")), Stub("b", ExternalServiceError("b", "down"))])
    with pytest.raises(ExternalServiceError) as err:
        chain.parse(system="s", user="u", schema=Answer, max_tokens=10)
    assert err.value.service == "b"


def test_fallback_needs_at_least_one_client():
    with pytest.raises(ValueError):
        FallbackLLMClient([])


# -- Amazon Nova via Bedrock Converse (no Marketplace card needed) ------------------------------
class FakeBoto:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.kwargs = response, error, None

    def converse(self, **kw):
        self.kwargs = kw
        if self.error:
            raise self.error
        return self.response


def nova_response(tool_input):
    return {"output": {"message": {"content": [{"toolUse": {"name": "submit_result", "input": tool_input}}]}},
            "usage": {"inputTokens": 40, "outputTokens": 9}, "stopReason": "tool_use"}


def test_nova_forces_tool_call_and_parses_result():
    from app.integrations.nova import BedrockNovaClient
    boto = FakeBoto(nova_response({"label": "FLOOD", "score": 4}))
    result = BedrockNovaClient("ap-south-1", "apac.amazon.nova-lite-v1:0", client=boto).parse(
        system="sys", user="usr", schema=Answer, max_tokens=300)
    assert boto.kwargs["toolConfig"]["toolChoice"] == {"tool": {"name": "submit_result"}}
    assert boto.kwargs["toolConfig"]["tools"][0]["toolSpec"]["inputSchema"]["json"]["properties"].keys() == {"label", "score"}
    assert boto.kwargs["system"] == [{"text": "sys"}] and boto.kwargs["inferenceConfig"]["maxTokens"] == 300
    assert result.parsed == Answer(label="FLOOD", score=4) and result.provider == "bedrock:apac.amazon.nova-lite-v1:0"
    assert result.usage == {"input_tokens": 40, "output_tokens": 9, "cache_read_input_tokens": 0}


def test_nova_invalid_tool_input_is_invalid_not_outage():
    from app.integrations.nova import BedrockNovaClient
    result = BedrockNovaClient("r", "m", client=FakeBoto(nova_response({"label": 3}))).parse(
        system="s", user="u", schema=Answer, max_tokens=10)
    assert result.parsed is None and not result.refused


def test_nova_aws_errors_become_external_errors():
    from botocore.exceptions import ClientError
    from app.integrations.nova import BedrockNovaClient
    err = ClientError({"Error": {"Code": "ThrottlingException", "Message": "slow"}}, "Converse")
    with pytest.raises(ExternalServiceError) as e:
        BedrockNovaClient("r", "m", client=FakeBoto(error=err)).parse(system="s", user="u", schema=Answer, max_tokens=10)
    assert e.value.service == "bedrock-nova" and "ThrottlingException" in str(e.value) and e.value.retryable


# -- Groq: long waits (daily quota) skip to the next provider instead of stalling ------------------
def test_groq_daily_quota_fails_fast_instead_of_sleeping():
    waits = []
    daily = httpx.Response(429, headers={"retry-after": "734"}, json={"error": {"code": "rate_limit_exceeded"}})
    client = GroqLLMClient("k", "openai/gpt-oss-120b", http=httpx.Client(transport=httpx.MockTransport(lambda r: daily)),
                           sleep=waits.append)
    with pytest.raises(ExternalServiceError) as e:
        client.parse(system="s", user="u", schema=Answer, max_tokens=10)
    assert waits == [] and "rate" in str(e.value).lower()


def test_groq_error_code_is_reported_without_secrets():
    bad = httpx.Response(400, json={"error": {"code": "json_validate_failed", "message": "schema mismatch"}})
    client = GroqLLMClient("gsk-secret", "m", http=httpx.Client(transport=httpx.MockTransport(lambda r: bad)),
                           sleep=lambda s: None)
    with pytest.raises(ExternalServiceError) as e:
        client.parse(system="s", user="u", schema=Answer, max_tokens=10)
    assert "json_validate_failed" in str(e.value) and "gsk-secret" not in str(e.value)
