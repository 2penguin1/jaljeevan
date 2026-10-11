"""Reading official drought declarations: turn taluka names in Marathi (or English) into our taluka ids.

Taluka names are proper nouns, so they are *transliterated* (Devanagari letters -> Latin letters), never
translated. A shared "latin key" then makes "सोलापूर" (solāpūra) and "Solapur" comparable, and a fuzzy score
says how sure we are. Low scores go to a person to check; nothing is guessed silently.
"""
import re
import unicodedata
from dataclasses import dataclass

from indic_transliteration import sanscript
from rapidfuzz import fuzz

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN1_JUNK = re.compile(r"[À-ÿ]")
_SPECIAL = str.maketrans({"ś": "sh", "ṣ": "sh", "ḻ": "l", "ḷ": "l", "ṃ": "n", "ṅ": "n", "ñ": "n", "ṇ": "n"})


def transliterate(text: str) -> str:
    """Devanagari -> IAST Latin; other text is returned unchanged."""
    return sanscript.transliterate(text, sanscript.DEVANAGARI, sanscript.IAST) if _DEVANAGARI.search(text) else text


def latin_key(name: str) -> str:
    """Spelling-insensitive key: lowercase, no accents, common sound-alikes merged, final schwa dropped."""
    s = name.lower().translate(_SPECIAL)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"[^a-z]", "", s)
    for a, b in (("aa", "a"), ("ee", "i"), ("oo", "u"), ("w", "v"), ("z", "j")):
        s = s.replace(a, b)
    return s[:-1] if len(s) > 3 and s.endswith("a") else s


def severity_from_text(english: str) -> str | None:
    """Severity words in (translated) order text: severe / moderate, or None if the text doesn't say."""
    t = english.lower()
    if re.search(r"\b(severe|serious|grave|acute)\b", t):
        return "severe"
    if re.search(r"\b(moderate|medium)\b", t):
        return "moderate"
    return None


def looks_garbled(text: str) -> bool:
    """PDFs typed in old Marathi fonts extract as Latin-1 junk instead of Devanagari; those pages need OCR."""
    letters = [c for c in text if c.isalpha()]
    if not letters or _DEVANAGARI.search(text):
        return False
    return len(_LATIN1_JUNK.findall(text)) / len(letters) > 0.2


@dataclass(frozen=True)
class TalukaMatch:
    area_id: int
    name: str
    district: str | None
    score: float  # 0-100


class TalukaMatcher:
    """Fuzzy-matches a taluka name (any script) against the talukas of one state."""

    ACCEPT = 85.0          # at or above: accepted automatically
    DISTRICT_SAME = 85.0   # how close a district name must be to count as "the same district"
    TIE = 5.0              # two candidates in different districts this close = ambiguous

    def __init__(self, talukas: list[tuple[int, str, str | None]]):
        self.talukas_raw = list(talukas)
        self.talukas = [(i, name, district, latin_key(name), latin_key(district or "")) for i, name, district in talukas]

    def match(self, text: str, district: str | None = None) -> TalukaMatch | None:
        key = latin_key(transliterate(text))
        if not key:
            return None
        pool, district_unmatched = self.talukas, False
        if district:
            dkey = latin_key(transliterate(district))
            in_district = [t for t in pool if fuzz.ratio(t[4], dkey) >= self.DISTRICT_SAME]
            pool, district_unmatched = (in_district, False) if in_district else (pool, True)
        ranked = sorted(pool, key=lambda t: fuzz.ratio(t[3], key), reverse=True)
        if not ranked:
            return None
        best, score = ranked[0], fuzz.ratio(ranked[0][3], key)
        rival = next((t for t in ranked[1:] if t[2] != best[2]), None)
        tied = rival is not None and score - fuzz.ratio(rival[3], key) < self.TIE
        if tied or district_unmatched:
            score = min(score, self.ACCEPT - 1)  # same name in another district, or an unreadable district: a person checks
        return TalukaMatch(best[0], best[1], best[2], score)
