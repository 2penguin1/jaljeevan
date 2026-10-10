"""Cheap rejection rules applied before any LLM cost. Each rule is a small Strategy object."""
from datetime import datetime, timedelta
from typing import Protocol

from app.domain.entities import RawItem
from app.domain.text import TextFingerprinter

KEYWORDS = (
    # English
    "water", "drought", "tanker", "borewell", "reservoir", "dry tap", "flood", "waterlog",
    "inundat", "cloudburst", "heatwave", "heat wave", "heatstroke", "heat stroke", "monsoon",
    # Hindi
    "पानी", "सूखा", "जल संकट", "टैंकर", "बाढ़", "हीटवेव", "गर्मी",
    # Marathi
    "पाणी", "दुष्काळ", "टँकर",
    # Kannada
    "ನೀರು", "ಬರಗಾಲ", "ಪ್ರವಾಹ",
    # Tamil
    "தண்ணீர்", "வறட்சி", "வெள்ளம்",
)

INDIA_HINTS = (
    "india", "भारत", "delhi", "mumbai", "bengaluru", "bangalore", "chennai", "kolkata",
    "hyderabad", "pune", "jaipur", "ahmedabad", "lucknow", "rajasthan", "maharashtra",
    "karnataka", "tamil nadu", "gujarat", "uttar pradesh", "bihar", "assam", "kerala", "odisha",
    "telangana", "andhra", "madhya pradesh", "punjab", "haryana", "west bengal", "jharkhand",
)


class PrefilterRule(Protocol):
    reason: str

    def rejects(self, item: RawItem, body: str, now: datetime) -> bool: ...


class EmptyRule:
    reason = "empty"

    def rejects(self, item: RawItem, body: str, now: datetime) -> bool:
        return not body.strip()


class MaxAgeRule:
    reason = "too_old"

    def __init__(self, max_age_days: int):
        self.max_age = timedelta(days=max_age_days)

    def rejects(self, item: RawItem, body: str, now: datetime) -> bool:
        return item.published_at is not None and now - item.published_at > self.max_age


class IndiaRule:
    """Foreign outlets pass only when the text itself mentions an Indian place."""

    reason = "not_india"

    def __init__(self, hints=INDIA_HINTS):
        self.hints = hints

    def rejects(self, item: RawItem, body: str, now: datetime) -> bool:
        foreign = item.country is not None and item.country.upper() != "IN"
        return foreign and not any(h in body for h in self.hints)


class KeywordRule:
    reason = "no_keyword"

    def __init__(self, keywords=KEYWORDS):
        self.keywords = tuple(TextFingerprinter.fold(k) for k in keywords)

    def rejects(self, item: RawItem, body: str, now: datetime) -> bool:
        return not any(k in body for k in self.keywords)


class Prefilter:
    """Runs rules in order; the first rule that rejects names the reason."""

    def __init__(self, rules: list[PrefilterRule], fingerprinter: TextFingerprinter | None = None):
        self.rules = rules
        self.fp = fingerprinter or TextFingerprinter()

    @classmethod
    def default(cls, max_age_days: int) -> "Prefilter":
        return cls([EmptyRule(), MaxAgeRule(max_age_days), IndiaRule(), KeywordRule()])

    def check(self, item: RawItem, now: datetime) -> str | None:
        body = self.fp.fold(self.fp.clean(f"{item.title} {item.text}"))
        for rule in self.rules:
            if rule.rejects(item, body, now):
                return rule.reason
        return None
