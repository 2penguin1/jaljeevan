import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.domain.entities import RawItem
from app.domain.prefilter import Prefilter
from app.domain.text import TextFingerprinter
from app.integrations.ports import RawArchive
from app.repositories.signal_repository import SignalRepository
from app.services.credibility_resolver import CredibilityResolver


@dataclass
class IngestResult:
    inserted: int = 0
    duplicate: int = 0
    near_duplicate: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    pending_ids: list[uuid.UUID] = field(default_factory=list)
    raw_key: str | None = None


class IngestionService:
    """Raw items -> stored signals: archive, prefilter, near-duplicate collapse, credibility, insert-if-new."""

    NEAR_DUP_WINDOW = timedelta(days=7)
    MIN_BODY_WORDS = 20
    HEADLINE_OVERLAP = 0.7  # 0.6 merged different wards' stories in testing

    def __init__(self, signals: SignalRepository, credibility: CredibilityResolver, prefilter: Prefilter,
                 fingerprinter: TextFingerprinter, archive: RawArchive):
        self.signals = signals
        self.credibility = credibility
        self.prefilter = prefilter
        self.fp = fingerprinter
        self.archive = archive

    def ingest(self, source: str, items: list[RawItem], now: datetime, run_id: str) -> IngestResult:
        result = IngestResult()
        if not items:
            return result
        result.raw_key = self.archive.save(source, items, run_id)
        recent = self.signals.recent_fingerprints(now - self.NEAR_DUP_WINDOW)
        rejected: Counter[str] = Counter()
        for item in items:
            self._ingest_one(item, now, recent, result, rejected)
        result.rejected = dict(rejected)
        return result

    def _has_body(self, item: RawItem) -> bool:
        return len(self.fp.clean(item.text).split()) >= self.MIN_BODY_WORDS

    def _find_original(self, item: RawItem, simhash: int, recent: list):
        """Wire copies keep the body (simhash match) or, when only a headline exists, re-word it (overlap)."""
        headline_only = not self._has_body(item)
        for sid, sh, title in recent:
            if self.fp.is_near_duplicate(sh, simhash):
                return sid
            if headline_only and self.fp.headline_similarity(item.title, title) >= self.HEADLINE_OVERLAP:
                return sid
        return None

    def _ingest_one(self, item: RawItem, now: datetime, recent: list, result: IngestResult,
                    rejected: Counter) -> None:
        full = self.fp.clean(f"{item.title}\n{item.text}")
        simhash = self.fp.simhash(self.fp.clean(item.text) if self._has_body(item) else full)
        reason = self.prefilter.check(item, now)
        dup_of = None
        if reason is None:
            dup_of = self._find_original(item, simhash, recent)
            reason = "near_duplicate" if dup_of else None
        new_id = self.signals.insert_if_new(
            source=item.source, url=item.url, domain=item.domain, author=item.author,
            title=self.fp.clean(item.title), text=self.fp.clean(item.text), lang=item.lang,
            published_at=item.published_at, content_hash=self.fp.content_hash(full), simhash=simhash,
            dup_of=dup_of, status="rejected" if reason else "pending", rejected_reason=reason,
            credibility=self.credibility.score(item.source, item.domain), raw_s3_key=result.raw_key,
            meta=item.meta or {})
        if new_id is None:
            result.duplicate += 1
            return
        result.inserted += 1
        if reason == "near_duplicate":
            result.near_duplicate += 1
        elif reason:
            rejected[reason] += 1
        else:
            result.pending_ids.append(new_id)
            recent.append((new_id, simhash, self.fp.clean(item.title)))
