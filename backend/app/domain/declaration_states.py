"""Reading drought declarations out of news text: which sentences list declared talukas, and which state they are in.

Rules come from real coverage (2026): the names sit in one sentence ("The 40 taluks added in the latest phase are A, B,
..., Y and Z"); headlines and demands mislead ("19 talukas declared" over a list that is only *demanded*, "may be
declared"), so a list counts only when its own sentence declares and does not hedge.
"""
import re
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class WatchState:
    code: str                # the state the declaration is about
    pool: str                # admin_areas.state_code whose talukas we match (Telangana mandals sit under AP)
    names: tuple[str, ...]   # how the press names the state


# Maharashtra is read from its official GR site (inbox); Bihar, Jharkhand, Odisha and West Bengal declare by block,
# which is not our unit, so they are left out on purpose.
WATCH_STATES: tuple[WatchState, ...] = (
    WatchState("KA", "KA", ("Karnataka", "K'taka", "Ktaka")),
    WatchState("TG", "AP", ("Telangana", "T'gana")),
    WatchState("AP", "AP", ("Andhra Pradesh", "Andhra")),
    WatchState("TN", "TN", ("Tamil Nadu",)),
    WatchState("GJ", "GJ", ("Gujarat",)),
    WatchState("RJ", "RJ", ("Rajasthan",)),
    WatchState("MP", "MP", ("Madhya Pradesh",)),
    WatchState("CT", "CT", ("Chhattisgarh",)),
    WatchState("UP", "UP", ("Uttar Pradesh",)),
    WatchState("KL", "KL", ("Kerala",)),
    WatchState("HR", "HR", ("Haryana",)),
    WatchState("PB", "PB", ("Punjab",)),
)

MIN_MATCHES = 3       # fewer names than this cannot tell us the state
MIN_SHARE = 0.6       # the winning state must hold this share of all matched names

_DECLARES = re.compile(r"declar|\badded\b|\bincluded\b|brought under|\bnotified\b|जाहीर|घोषित", re.I)
_HEDGE = re.compile(
    r"\b(?:demand\w*|may|might|likely|could|would|should|seek\w*|sought|urg\w*|exclu\w*|left out|outside|protest\w*|"
    r"warn\w*|propos\w*|recommend\w*|expected|yet to|if not|not declared|withdraw\w*|will|to be|set to|plan\w*|"
    r"not yet|not been|soon)\b|मागणी|प्रस्ताव|वगळ|समावेश करा",
    re.I)
_MARKER = re.compile(r"\b(?:are|is|include|includes|including|namely)\b|:")
_UNIT = r"(?:taluks?|talukas?|mandals?|tehsils?|tahsils?)"
_SINGLE = re.compile(rf"^(?:The\s+)?([A-Z][\w-]+(?:\s[A-Z][\w-]+)?)\s+{_UNIT}\b")
_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")
_ITEM_SPLIT = re.compile(r",|;|&|،|\band\b|\bव\b")
_UNIT_WORD = re.compile(rf"\s+{_UNIT}$|^{_UNIT}\s+(?:of\s+)?", re.I)
_LETTER = re.compile(r"[A-Za-zऀ-෿]")


@dataclass(frozen=True)
class ListSentence:
    text: str
    names: list[str]


def declares(sentence: str) -> bool:
    return bool(_DECLARES.search(sentence))


def is_hedged(sentence: str) -> bool:
    return bool(_HEDGE.search(sentence))


def list_sentences(text: str) -> list[ListSentence]:
    """Sentences that declare talukas, with the names they list. A declaring line that ends in ':' introduces the
    list on the next line."""
    out: list[ListSentence] = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for i, line in enumerate(lines):
        for sentence in _SENTENCE_END.split(line):
            if not declares(sentence) or is_hedged(sentence):
                continue
            names = _names(sentence)
            if not names and sentence.rstrip().endswith(":") and i + 1 < len(lines) and not is_hedged(lines[i + 1]):
                names = _items(lines[i + 1])
            if names:
                out.append(ListSentence(sentence, names))
    return out


def _names(sentence: str) -> list[str]:
    markers = list(_MARKER.finditer(sentence))
    listed = _items(sentence[markers[-1].end():]) if markers else []
    if listed:
        return listed
    single = _SINGLE.match(sentence)
    return [single.group(1)] if single else []


def _items(text: str) -> list[str]:
    """Comma / 'and' separated names; anything that reads like prose (digits, more than three words) is dropped."""
    out = []
    for raw in _ITEM_SPLIT.split(text):
        item = _UNIT_WORD.sub("", raw.strip(" .;:-–'\"”“")).strip(" .")
        words = item.split()
        if not words or len(words) > 3 or re.search(r"\d", item) or not _LETTER.match(item):
            continue
        if item[0].isascii() and not item[0].isupper():  # English names are capitalised; "the list" is not a name
            continue
        out.append(item)
    return out


def names_state(text: str, state: WatchState) -> bool:
    folded = text.replace("’", "'")
    return any(re.search(rf"\b{re.escape(n)}\b", folded, re.I) for n in state.names)


def pick_state(counts: dict[str, tuple[int, int]], text: str) -> WatchState | None:
    """counts[pool] = (distinct talukas matched, list items) per boundary pool. The pool with most matches wins only
    with enough names, a clear share, and the state's name in the article; never guessed from names alone. A short
    article (one or two talukas) counts only when it names exactly one watched state and every match is in it."""
    if not counts:
        return None
    pool, (best, _) = max(counts.items(), key=lambda kv: kv[1][0])
    total = sum(accepted for accepted, _ in counts.values())
    named = [s for s in WATCH_STATES if names_state(text, s)]
    if best < MIN_MATCHES:
        if not (len(named) == 1 and named[0].pool == pool and best == total):
            return None
    elif best / total < MIN_SHARE:
        return None
    return next((s for s in named if s.pool == pool), None)


_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                       "dec"), start=1)}
# Devanagari, Bengali, Gurmukhi, Gujarati, Oriya, Tamil, Telugu, Kannada, Malayalam digits -> 0-9
_INDIC_DIGITS = str.maketrans({chr(base + d): str(d) for base in (0x0966, 0x09E6, 0x0A66, 0x0AE6, 0x0B66, 0x0BE6,
                                                                   0x0C66, 0x0CE6, 0x0D66) for d in range(10)})
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d\d)\b|\b(20\d\d)-(\d{2})-(\d{2})\b")
_WORD_DATE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?"
                        r"\s+(20\d\d)\b", re.I)


def order_dates(text: str) -> list[date]:
    """Dates written in an order (12/09/2023, 2026-09-28, 28 September 2026; Indian digits too), oldest first."""
    folded = text.translate(_INDIC_DIGITS)
    found = []
    for m in _NUMERIC_DATE.finditer(folded):
        d, mo, y = (m.group(1), m.group(2), m.group(3)) if m.group(3) else (m.group(6), m.group(5), m.group(4))
        found.append((int(y), int(mo), int(d)))
    found += [(int(m.group(3)), _MONTHS[m.group(2).lower()[:3]], int(m.group(1))) for m in _WORD_DATE.finditer(folded)]
    out = set()
    for y, mo, d in found:
        try:
            out.add(date(y, mo, d))
        except ValueError:
            continue
    return sorted(out)
