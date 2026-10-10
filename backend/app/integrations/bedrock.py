from pydantic import BaseModel

from app.integrations.ports import LLMResult


class BedrockLLMClient:
    """Adapter over Claude on Amazon Bedrock (structured output + prompt caching).

    Uses the legacy bedrock-runtime client because it accepts inference-profile IDs such as
    "in.anthropic.claude-haiku-4-5-20251001-v1:0" (the Claude model available on the free plan).
    """

    # Models that reject output_config.effort (Haiku 4.5 and older).
    _NO_EFFORT = ("haiku-4-5", "sonnet-4-5", "claude-3")

    def __init__(self, region: str, profile: str | None = None, effort: str = "low", cache_system: bool = True):
        from anthropic import AnthropicBedrock

        self.client = AnthropicBedrock(aws_region=region, aws_profile=profile)
        self.effort = effort
        self.cache_system = cache_system

    def parse(self, *, system: str, user: str, schema: type[BaseModel], model: str, max_tokens: int) -> LLMResult:
        extra = {} if any(m in model for m in self._NO_EFFORT) else {"output_config": {"effort": self.effort}}
        system_blocks = [{"type": "text", "text": system,
                          **({"cache_control": {"type": "ephemeral"}} if self.cache_system else {})}]
        resp = self.client.messages.parse(
            model=model, max_tokens=max_tokens, system=system_blocks,
            messages=[{"role": "user", "content": user}], output_format=schema, **extra)
        usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens,
                 "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", 0) or 0}
        if resp.stop_reason == "refusal":
            return LLMResult(parsed=None, usage=usage, refused=True)
        return LLMResult(parsed=resp.parsed_output, usage=usage)
