import logging

from pydantic import BaseModel

from app.core.exceptions import ExternalServiceError
from app.integrations.ports import LLMClient, LLMResult

LOG = logging.getLogger(__name__)


class FallbackLLMClient:
    """Chain of LLM providers behind the same LLMClient interface (Chain of Responsibility / Decorator).

    Moves to the next provider only on availability failures (ExternalServiceError). A refusal is a
    decision, not an outage, so it is returned as-is and never retried on another model.
    """

    def __init__(self, clients: list[LLMClient]):
        if not clients:
            raise ValueError("FallbackLLMClient needs at least one client")
        self.clients = clients

    def parse(self, *, system: str, user: str, schema: type[BaseModel], max_tokens: int) -> LLMResult:
        last_error: ExternalServiceError | None = None
        for client in self.clients:
            try:
                return client.parse(system=system, user=user, schema=schema, max_tokens=max_tokens)
            except ExternalServiceError as exc:
                LOG.warning("LLM provider %s unavailable (%s); trying next", getattr(client, "provider", client), exc)
                last_error = exc
        raise last_error
