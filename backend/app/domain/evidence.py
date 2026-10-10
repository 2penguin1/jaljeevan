import re
from dataclasses import dataclass

from app.domain.classification import Label
from app.domain.taxonomy import Taxonomy
from app.domain.text import TextFingerprinter


@dataclass(frozen=True)
class ValidLabel:
    code: str
    l1_code: str
    severity: int
    evidence: str


class EvidenceValidator:
    """Anti-hallucination gate: a label survives only if its quote appears verbatim in the post.

    Comparison is NFC + casefold + collapsed whitespace, so Indic scripts and casing differences pass.
    Unknown codes are dropped, severity is clamped to 1..5, and one quote cannot back unrelated L1s.
    """

    _WS = re.compile(r"\s+")

    def __init__(self, taxonomy: Taxonomy, fingerprinter: TextFingerprinter | None = None):
        self.taxonomy = taxonomy
        self.fp = fingerprinter or TextFingerprinter()

    def _norm(self, text: str) -> str:
        return self._WS.sub(" ", self.fp.fold(text)).strip()

    def validate(self, post_text: str, labels: list[Label]) -> list[ValidLabel]:
        haystack = self._norm(post_text)
        kept: dict[str, ValidLabel] = {}  # one label per code (the table's primary key), most severe wins
        quote_owner: dict[str, str] = {}
        for label in labels:
            l1 = self.taxonomy.parent_of(label.code)
            quote = self._norm(label.evidence)
            if l1 is None or not quote or quote not in haystack:
                continue
            if quote_owner.setdefault(quote, l1) != l1:
                continue
            candidate = ValidLabel(label.code, l1, min(5, max(1, label.severity)), label.evidence.strip())
            if label.code not in kept or candidate.severity > kept[label.code].severity:
                kept[label.code] = candidate
        return list(kept.values())
