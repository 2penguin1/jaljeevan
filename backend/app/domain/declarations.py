"""Reading official drought declarations: turn taluka names in Marathi (or English) into our taluka ids.

Taluka names are proper nouns, so they are *transliterated* (Devanagari letters -> Latin letters), never
translated. A shared "latin key" then makes "सोलापूर" (solāpūra) and "Solapur" comparable, and a fuzzy score
says how sure we are. Low scores go to a person to check; nothing is guessed silently.
"""
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace
from itertools import product

from indic_transliteration import sanscript
from rapidfuzz import fuzz

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN1_JUNK = re.compile(r"[À-ÿ]")
_SPECIAL = str.maketrans({"ś": "sh", "ṣ": "sh", "ḻ": "l", "ḷ": "l", "ṃ": "n", "ṅ": "n", "ñ": "n", "ṇ": "n"})


# Indian scripts sit in consecutive 128-letter Unicode blocks from U+0900; official orders of other states use these
_SCRIPTS = {0x0900: sanscript.DEVANAGARI, 0x0980: sanscript.BENGALI, 0x0A00: sanscript.GURMUKHI,
            0x0A80: sanscript.GUJARATI, 0x0B00: sanscript.ORIYA, 0x0B80: sanscript.TAMIL, 0x0C00: sanscript.TELUGU,
            0x0C80: sanscript.KANNADA, 0x0D00: sanscript.MALAYALAM}


def transliterate(text: str) -> str:
    """Indian-script text (Marathi, Kannada, Telugu, ...) -> IAST Latin; other text is returned unchanged."""
    block = next((ord(c) & ~0x7F for c in text if 0x0900 <= ord(c) < 0x0D80), None)
    return sanscript.transliterate(text, _SCRIPTS[block], sanscript.IAST) if block is not None else text


# Government PDFs often use fonts whose glyphs map to the wrong Unicode letters when text is extracted. Seen in
# real Maharashtra GRs (each fix is applied only where the broken form cannot be valid Devanagari, or tried as an
# extra variant next to the original):
#   ग before a vowel sign / anusvara / word end      -> र्       (सांगोला -> सांर्ोला)
#   न or श where a vowel sign cannot stand            -> ि        (जामनेर -> जामिेर, शेवगाव -> िेवगाव, वाशीम -> वािीम)
#   र् (reph) written after its letter                -> ध        (कर्जत -> कजधत, दोडामार्ग -> दोडामागध)
#   the vowel sign ि (drawn before its letter)        -> a stray ज, न or स in front (शिरूर -> जशरूर, हिंगोली -> सहगोली)
_CONSONANT = "[\u0915-\u0939]"
_BROKEN_GA = re.compile(r"र्(?=[\u093E-\u094C\u0902\u0901]|$|\s)")
_BROKEN_NA = re.compile(r"(?:(?<=^)|(?<=\s))\u093F|\u093F(?=[\u093E-\u094C\u0902\u0901])")
_BROKEN_REPH = re.compile(f"({_CONSONANT})ध")
# a stray ज/न is never the second half of a conjunct (preceded by ्), so real न्न / ज्ज stay intact
_BROKEN_I_JA = re.compile(f"(?<!्)ज({_CONSONANT})")
_BROKEN_I_NA = re.compile(f"(?<!्)न({_CONSONANT})")
_BROKEN_I_SA = re.compile(f"(?<!्)स({_CONSONANT})")


_BROKEN_SHI = re.compile("नि")  # शि extracted as नि (शिरपूर -> निरपूर)


def _broken_i_readings(text: str) -> list[str]:
    """Every reading of a misplaced ि as न or श, one by one (िागपूर िहर = नागपूर शहर); capped for long lines."""
    parts = _BROKEN_NA.split(text)
    if len(parts) > 4:
        return [_BROKEN_NA.sub(c, text) for c in "नश"]
    return ["".join(p + c for p, c in zip(parts, combo + ("",))) for combo in product("नश", repeat=len(parts) - 1)]


def pdf_repairs(text: str) -> list[str]:
    """The text plus repaired spellings. Callers match every variant and keep the best score, so genuine letters
    (e.g. Jath taluka, जत, or a real ध) are never damaged: the original spelling competes too, unless it is
    impossible Devanagari (र् or ि before a vowel sign), where only its repairs can be right."""
    impossible = bool(_BROKEN_GA.search(text) or _BROKEN_NA.search(text))
    variants = [] if impossible else [text]
    for ra in ("ग", "ण", "ध"):  # a broken र् stands for ग, ण or ध depending on the font (ठाणे -> ठार्े)
        for safe in _broken_i_readings(_BROKEN_GA.sub(ra, text)):
            reph = _BROKEN_REPH.sub("र्\\1", safe)
            stray_na = _BROKEN_I_NA.sub("\\1\u093F", reph)
            variants += [safe, reph, _BROKEN_I_JA.sub("\\1\u093F", reph), stray_na,
                         _BROKEN_I_SA.sub("\\1\u093F", reph), _BROKEN_SHI.sub("शि", reph),
                         _BROKEN_SHI.sub("शि", stray_na)]
    return list(dict.fromkeys(variants))


def latin_alternates(name: str) -> set[str]:
    """Keys for English spellings that drop a Marathi sound: गेवराई 'gevarai' is officially 'Georai', and the
    unwritten middle vowel of जालना 'jālanā' is dropped in 'Jalna'."""
    keys = {latin_key(name), latin_key(name, drop_schwa=True)}
    return keys | {re.sub(r"eva", "eo", k) for k in keys}


def latin_key(name: str, drop_schwa: bool = False) -> str:
    """Spelling-insensitive key: lowercase, no accents, common sound-alikes merged, final schwa dropped."""
    s = name.lower().translate(_SPECIAL)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"[^a-z]", "", s)
    for a, b in (("aa", "a"), ("ee", "i"), ("oo", "u"), ("w", "v"), ("z", "j")):
        s = s.replace(a, b)
    s = re.sub(r"n(?=[bp])", "m", s)  # anusvara before b/p is spoken "m": कळंब kaḷaṃb -> Kalamb
    if drop_schwa:  # vowel-consonant-a-consonant-vowel: the "a" is not spoken (jalana -> jalna)
        s = re.sub(r"(?<=[aeiou][^aeiou])a(?=[^aeiou][aeiou])", "", s)
    s = re.sub(r"gaon$|gaum$", "gav", s)  # official English "-gaon" = Marathi "-गाव" (Malegaon / मालेगाव)
    s = s[:-1] if len(s) > 3 and s.endswith("a") else s
    return re.sub(r"(?<=[^aeiou])a(?=[^aeiou]a?v$)", "", s)  # medial schwa before -gav: jalagav -> jalgav


def severity_from_text(english: str) -> str | None:
    """Severity words in order text (English, or Marathi: गंभीर = severe, मध्यम = moderate), or None."""
    t = english.lower()
    if re.search(r"\b(severe|serious|grave|acute)\b", t) or re.search(r"गंभीर|तीव्र", english):
        return "severe"
    if re.search(r"\b(moderate|medium)\b", t) or "मध्यम" in english:
        return "moderate"
    return None


def looks_garbled(text: str) -> bool:
    """PDFs typed in old Marathi fonts extract as Latin-1 junk instead of Devanagari; those pages need OCR."""
    letters = [c for c in text if c.isalpha()]
    if not letters or _DEVANAGARI.search(text):
        return False
    return len(_LATIN1_JUNK.findall(text)) / len(letters) > 0.2


# places renamed after our boundary data was published: new official name -> name in admin_areas
RENAMED = {"Dharashiv": "Osmanabad", "Sambhajinagar": "Aurangabad", "Chhatrapati Sambhajinagar": "Aurangabad",
           "Ahilyanagar": "Ahmednagar"}
# how Marathi orders write the suffixes in our taluka names: plain = rural, शहर = city, उ./द. = north/south
_SUFFIX_FORMS = {"(Rural)": ("{}",), "(Urban)": ("{} shahar",), "City": ("{} shahar",),
                 "North": ("u {}", "uttar {}"), "South": ("d {}", "dakshin {}")}


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
    TIE = 5.0              # two different talukas this close = ambiguous
    ALIAS_DISTINCT = 90.0  # a first-word alias this close to another taluka's name is not used

    def __init__(self, talukas: list[tuple[int, str, str | None]]):
        self.talukas_raw = list(talukas)
        firsts = Counter(latin_key(name.split()[0]) for _, name, _ in talukas if " " in name)
        taken = {latin_key(name) for _, name, _ in talukas} | {w for w, n in firsts.items() if n > 1}
        self.talukas = [(i, name, district, self._keys(name, taken), latin_key(district or ""))
                        for i, name, district in talukas]

    @staticmethod
    def _keys(name: str, taken: set[str]) -> set[str]:
        """The name's key, its new official name, the way orders write its suffix ("Solapur North" = "उ. सोलापूर"),
        and its first word ("Dhamangaon Railway" -> "Dhamangaon") unless another taluka starts with that word or has
        a name like it ("Jalgaon (Jamod)" must not become "Jalgaon", "Sindkhed Raja" must not look like Sindkhede)."""
        keys = {latin_key(name)} | {latin_key(new) for new, old in RENAMED.items() if old == name}
        base, _, suffix = name.rpartition(" ")
        keys |= {latin_key(form.format(base)) for form in _SUFFIX_FORMS.get(suffix, ())}
        first = latin_key(name.split()[0])
        distinct = not any(fuzz.ratio(first, k) >= TalukaMatcher.ALIAS_DISTINCT for k in taken - {latin_key(name)})
        return keys | ({first} if " " in name and distinct else set())

    def match(self, text: str, district: str | None = None) -> TalukaMatch | None:
        hits = sorted((h for v in pdf_repairs(text) if (h := self._match_one(v, district))),
                      key=lambda h: h.score, reverse=True)
        if not hits:
            return None
        best = hits[0]
        # two repairs reading two different talukas equally well (वािी = वानी Wani or वाशी Washi): a person checks
        rival = next((h for h in hits[1:] if h.area_id != best.area_id), None)
        if rival is not None and best.score - rival.score < self.TIE:
            return replace(best, score=min(best.score, self.ACCEPT - 1))
        return best

    def _match_one(self, text: str, district: str | None) -> TalukaMatch | None:
        latin = transliterate(text)
        if not latin_key(latin):
            return None
        pool, district_unmatched = self.talukas, False
        if district:
            dkey = latin_key(transliterate(district))
            in_district = [t for t in pool if fuzz.ratio(t[4], dkey) >= self.DISTRICT_SAME]
            pool, district_unmatched = (in_district, False) if in_district else (pool, True)
        keys = latin_alternates(latin)

        def similarity(t) -> float:
            return max(fuzz.ratio(name, k) for name in t[3] for k in keys)

        ranked = sorted(pool, key=similarity, reverse=True)
        if not ranked:
            return None
        best, score = ranked[0], similarity(ranked[0])
        rival = next((t for t in ranked[1:] if t[0] != best[0]), None)
        tied = rival is not None and score - similarity(rival) < self.TIE
        if tied or district_unmatched:
            score = min(score, self.ACCEPT - 1)  # another taluka just as close, or an unreadable district: a person checks
        return TalukaMatch(best[0], best[1], best[2], score)
