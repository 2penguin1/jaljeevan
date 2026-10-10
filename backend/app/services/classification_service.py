import dataclasses
import logging
import uuid
from dataclasses import dataclass
from datetime import date

from app.domain.classification import BatchResult, PostInput, PostResult, PromptBuilder
from app.domain.evidence import EvidenceValidator
from app.domain.taxonomy import Taxonomy
from app.integrations.ports import LLMClient
from app.models import Signal
from app.repositories.signal_repository import SignalRepository

LOG = logging.getLogger(__name__)


@dataclass
class ClassificationStats:
    classified: int = 0
    unclear: int = 0
    irrelevant: int = 0
    failed: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


class ClassificationService:
    """Sends pending signals to the LLM in batches, validates evidence, and persists labels + locations.

    Failure isolation: an error, refusal or missing answer marks only the affected signals as failed.
    """

    PROMPT_VERSION = "p1"
    BATCH_SIZE = 10
    MIN_WORDS = 3
    MAX_TOKENS = 8000

    def __init__(self, signals: SignalRepository, llm: LLMClient, prompts: PromptBuilder,
                 validator: EvidenceValidator, taxonomy: Taxonomy, model: str):
        self.signals = signals
        self.llm = llm
        self.prompts = prompts
        self.validator = validator
        self.taxonomy = taxonomy
        self.model = model

    @property
    def classifier_version(self) -> str:
        return f"{self.taxonomy.version[:8]}{self.PROMPT_VERSION}"

    def classify(self, signal_ids, contrasts=(), raise_errors: bool = False) -> ClassificationStats:
        stats = ClassificationStats()
        ids = list(signal_ids)
        order = {sid: i for i, sid in enumerate(ids)}
        signals = sorted(self.signals.get_many(ids), key=lambda s: order[s.id])
        todo = [s for s in signals if not self._too_short(s, stats)]
        system = self.prompts.system(contrasts)
        try:
            for i in range(0, len(todo), self.BATCH_SIZE):
                self._classify_batch(todo[i:i + self.BATCH_SIZE], system, stats, raise_errors)
        finally:
            self.signals.flush()
        return stats

    # -- internals ------------------------------------------------------------------------------
    def _too_short(self, signal: Signal, stats: ClassificationStats) -> bool:
        if len(f"{signal.title} {signal.text}".split()) >= self.MIN_WORDS:
            return False
        signal.status, signal.rejected_reason = "unclear", "too_short"
        stats.unclear += 1
        return True

    def _classify_batch(self, batch: list[Signal], system: str, stats: ClassificationStats,
                        raise_errors: bool) -> None:
        posts = [PostInput(str(s.id), s.source, s.published_at, s.title, s.text) for s in batch]
        user, id_map = self.prompts.user(posts)
        try:
            res = self.llm.parse(system=system, user=user, schema=BatchResult, model=self.model,
                                 max_tokens=self.MAX_TOKENS)
        except Exception as exc:  # noqa: BLE001 - any provider failure isolates this batch only
            if raise_errors:
                raise
            LOG.warning("classification batch failed: %r", exc)
            self._fail_all(batch, f"llm_error:{type(exc).__name__}", stats)
            return
        stats.input_tokens += res.usage.get("input_tokens", 0)
        stats.output_tokens += res.usage.get("output_tokens", 0)
        stats.cache_read_tokens += res.usage.get("cache_read_input_tokens", 0)
        if res.refused or res.parsed is None:
            self._fail_all(batch, "llm_refused" if res.refused else "llm_invalid", stats)
            return
        answers = {r.id: r for r in res.parsed.results}
        by_key = {str(s.id): s for s in batch}
        for pid, key in id_map.items():
            if pid in answers:
                self._apply(by_key[key], answers[pid], stats)
            else:
                self._fail(by_key[key], "llm_missing", stats)

    def _apply(self, signal: Signal, result: PostResult, stats: ClassificationStats) -> None:
        labels = self.validator.validate(f"{signal.title}\n{signal.text}", result.labels)
        self.signals.replace_labels(signal.id, [dataclasses.asdict(l) for l in labels])
        l1_codes = sorted({l.l1_code for l in labels})
        signal.relevant = result.relevant
        signal.event_period, signal.event_date = result.event_period, self._safe_date(result.event_date)
        signal.first_hand, signal.english_summary = result.first_hand, result.english_summary
        signal.people_affected_hint = result.people_affected_hint if (result.people_affected_hint or 0) > 0 else None
        signal.l1_codes, signal.hazards = l1_codes, self.taxonomy.hazards_for(l1_codes)
        signal.max_severity = max((l.severity for l in labels), default=None)
        signal.classifier_version = self.classifier_version
        signal.meta = {**(signal.meta or {}), "locations": [m.model_dump() for m in result.locations]}
        signal.rejected_reason = None
        if not result.relevant:
            signal.status = "classified"
            stats.irrelevant += 1
        elif not labels:
            signal.status = "unclear"
            stats.unclear += 1
        else:
            signal.status = "classified"
            stats.classified += 1

    def _fail_all(self, batch: list[Signal], reason: str, stats: ClassificationStats) -> None:
        for signal in batch:
            self._fail(signal, reason, stats)

    @staticmethod
    def _fail(signal: Signal, reason: str, stats: ClassificationStats) -> None:
        signal.status, signal.rejected_reason = "failed", reason
        stats.failed += 1

    @staticmethod
    def _safe_date(value: str | None) -> date | None:
        try:
            return date.fromisoformat(value[:10]) if value else None
        except ValueError:
            return None
