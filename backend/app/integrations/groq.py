import re
import time
from collections.abc import Callable

import httpx
from pydantic import BaseModel, ValidationError

from app.core.exceptions import ExternalServiceError
from app.integrations.ports import LLMResult


def _seconds(value: str | None) -> float | None:
    """Parse Groq reset headers: '7', '577ms', '1m26.4s' -> seconds."""
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        pass
    total, matched = 0.0, False
    for amount, unit in re.findall(r"([\d.]+)(ms|h|m|s)", value):
        matched = True
        total += float(amount) * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[unit]
    return total if matched else None


class GroqLLMClient:
    """Adapter over Groq's OpenAI-compatible Chat Completions API (outside AWS).

    Plain HTTP, no extra SDK. Free-tier limits are small (e.g. 8,000 tokens/minute), so HTTP 429 is waited out
    using Groq's own retry-after / token-reset headers before giving up. The answer is validated with the same
    Pydantic schema, so a malformed answer becomes parsed=None (llm_invalid), not an outage.
    """

    URL = "https://api.groq.com/openai/v1/chat/completions"
    MAX_RETRIES = 3
    DEFAULT_WAIT_S = 10.0

    def __init__(self, api_key: str, model: str, http: httpx.Client | None = None, timeout: float = 60,
                 sleep: Callable[[float], None] = time.sleep):
        self.api_key = api_key
        self.model = model
        self.http = http or httpx.Client(timeout=timeout)
        self.sleep = sleep

    @property
    def provider(self) -> str:
        return f"groq:{self.model}"

    def parse(self, *, system: str, user: str, schema: type[BaseModel], max_tokens: int) -> LLMResult:
        body = {"model": self.model, "max_completion_tokens": max_tokens, "temperature": 0,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()}}}
        if "gpt-oss" in self.model:
            body["reasoning_effort"] = "low"  # short hidden reasoning: fewer tokens against the per-minute limit
        res = self._post_with_backoff(body)
        data = res.json()
        message = (data.get("choices") or [{}])[0].get("message") or {}
        raw_usage = data.get("usage") or {}
        usage = {"input_tokens": raw_usage.get("prompt_tokens", 0),
                 "output_tokens": raw_usage.get("completion_tokens", 0), "cache_read_input_tokens": 0}
        if message.get("refusal"):
            return LLMResult(parsed=None, usage=usage, refused=True, provider=self.provider)
        try:
            parsed = schema.model_validate_json(message.get("content") or "")
        except ValidationError:
            parsed = None
        return LLMResult(parsed=parsed, usage=usage, provider=self.provider)

    def _post_with_backoff(self, body: dict) -> httpx.Response:
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                res = self.http.post(self.URL, json=body, headers={"Authorization": f"Bearer {self.api_key}"})
            except httpx.HTTPError as exc:
                raise ExternalServiceError("groq", f"request failed ({type(exc).__name__})") from None
            if res.status_code == 429 and attempt < self.MAX_RETRIES:
                wait = (_seconds(res.headers.get("retry-after"))
                        or _seconds(res.headers.get("x-ratelimit-reset-tokens")) or self.DEFAULT_WAIT_S)
                self.sleep(wait)
                continue
            if res.status_code >= 400:  # never echo the response or headers: keep the key out of messages
                raise ExternalServiceError("groq", f"HTTP {res.status_code}",
                                           retryable=res.status_code == 429 or res.status_code >= 500)
            return res
        raise ExternalServiceError("groq", "HTTP 429 after retries")  # unreachable; keeps type checkers calm
