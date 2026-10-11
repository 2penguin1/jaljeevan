"""Ask the AI with a deadline, for requests a person is waiting on.

The shared LLM client may wait out rate limits for minutes (fine for the pipeline). A person clicking "Draft" must
get an answer well inside CloudFront's 60 s limit, so interactive calls give up after a deadline and the caller falls
back to its template. A late answer is simply ignored.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from app.integrations.ports import LLMClient, LLMResult

LOG = logging.getLogger(__name__)
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ai-deadline")


def ask(llm: LLMClient | None, deadline_s: float, **kwargs) -> LLMResult | None:
    if llm is None:
        return None
    future = _POOL.submit(llm.parse, **kwargs)
    try:
        return future.result(timeout=deadline_s)
    except FutureTimeout:
        LOG.warning("AI answer took longer than %.0f s; using the template", deadline_s)
        return None
    except Exception:  # noqa: BLE001 - any AI failure falls back to the template
        LOG.exception("AI call failed; using the template")
        return None
