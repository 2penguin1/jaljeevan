from pydantic import BaseModel, ValidationError

from app.core.exceptions import ExternalServiceError
from app.integrations.ports import LLMResult


class BedrockLLMClient:
    """Adapter over Claude on Amazon Bedrock with prompt caching.

    Structured output strategy depends on the model:
      * Haiku 4.5 and older: a forced tool call whose input_schema is our JSON schema. (Bedrock's
        structured-output API returned HTTP 500 for Haiku 4.5 in live testing.)
      * newer models: the structured-output API (messages.parse + output_format) with effort control.
    Either way the answer is re-validated with the Pydantic schema; a mismatch is parsed=None, not an outage.
    """

    TOOL_NAME = "submit_result"
    _LEGACY = ("haiku-4-5", "sonnet-4-5", "claude-3")  # no output_format / effort support on Bedrock

    def __init__(self, region: str, model: str, profile: str | None = None, effort: str = "low",
                 cache_system: bool = True, client=None):
        if client is None:
            from anthropic import AnthropicBedrock
            client = AnthropicBedrock(aws_region=region, aws_profile=profile)
        self.client = client
        self.model = model
        self.effort = effort
        self.cache_system = cache_system

    @property
    def provider(self) -> str:
        return f"bedrock:{self.model}"

    @property
    def _legacy(self) -> bool:
        return any(m in self.model for m in self._LEGACY)

    def parse(self, *, system: str, user: str, schema: type[BaseModel], max_tokens: int) -> LLMResult:
        import anthropic

        system_blocks = [{"type": "text", "text": system,
                          **({"cache_control": {"type": "ephemeral"}} if self.cache_system else {})}]
        messages = [{"role": "user", "content": user}]
        try:
            if self._legacy:
                resp = self.client.messages.create(
                    model=self.model, max_tokens=max_tokens, system=system_blocks, messages=messages,
                    tools=[{"name": self.TOOL_NAME, "description": "Return the classification result.",
                            "input_schema": schema.model_json_schema()}],
                    tool_choice={"type": "tool", "name": self.TOOL_NAME})
            else:
                resp = self.client.messages.parse(
                    model=self.model, max_tokens=max_tokens, system=system_blocks, messages=messages,
                    output_format=schema, output_config={"effort": self.effort})
        except anthropic.APIStatusError as exc:  # access denied, form missing, throttled, outage
            raise ExternalServiceError("bedrock", f"HTTP {exc.status_code}",
                                       retryable=exc.status_code in (408, 429) or exc.status_code >= 500) from None
        except anthropic.APIConnectionError as exc:
            raise ExternalServiceError("bedrock", f"connection failed ({type(exc).__name__})") from None
        usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens,
                 "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", 0) or 0}
        if resp.stop_reason == "refusal":
            return LLMResult(parsed=None, usage=usage, refused=True, provider=self.provider)
        parsed = self._tool_answer(resp, schema) if self._legacy else resp.parsed_output
        return LLMResult(parsed=parsed, usage=usage, provider=self.provider)

    def _tool_answer(self, resp, schema: type[BaseModel]) -> BaseModel | None:
        block = next((b for b in resp.content if getattr(b, "type", "") == "tool_use"
                      and getattr(b, "name", "") == self.TOOL_NAME), None)
        if block is None:
            return None
        try:
            return schema.model_validate(block.input)
        except ValidationError:
            return None
