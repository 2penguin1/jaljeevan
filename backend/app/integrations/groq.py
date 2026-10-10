import httpx
from pydantic import BaseModel, ValidationError

from app.core.exceptions import ExternalServiceError
from app.integrations.ports import LLMResult


class GroqLLMClient:
    """Adapter over Groq's OpenAI-compatible Chat Completions API (fallback provider, outside AWS).

    Plain HTTP: no extra SDK. The JSON schema is sent as response_format; the answer is still validated
    with the same Pydantic schema, so a malformed answer becomes parsed=None (llm_invalid), not an outage.
    """

    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str, http: httpx.Client | None = None, timeout: float = 60):
        self.api_key = api_key
        self.model = model
        self.http = http or httpx.Client(timeout=timeout)

    @property
    def provider(self) -> str:
        return f"groq:{self.model}"

    def parse(self, *, system: str, user: str, schema: type[BaseModel], max_tokens: int) -> LLMResult:
        body = {"model": self.model, "max_completion_tokens": max_tokens, "temperature": 0,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()}}}
        try:
            res = self.http.post(self.URL, json=body, headers={"Authorization": f"Bearer {self.api_key}"})
        except httpx.HTTPError as exc:
            raise ExternalServiceError("groq", f"request failed ({type(exc).__name__})") from None
        if res.status_code >= 400:  # never echo the response or headers: keep the key out of messages
            raise ExternalServiceError("groq", f"HTTP {res.status_code}",
                                       retryable=res.status_code == 429 or res.status_code >= 500)
        data = res.json()
        message = (data.get("choices") or [{}])[0].get("message") or {}
        usage = data.get("usage") or {}
        usage = {"input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0),
                 "cache_read_input_tokens": 0}
        if message.get("refusal"):
            return LLMResult(parsed=None, usage=usage, refused=True, provider=self.provider)
        try:
            parsed = schema.model_validate_json(message.get("content") or "")
        except ValidationError:
            parsed = None
        return LLMResult(parsed=parsed, usage=usage, provider=self.provider)
