"""Pulls (district, taluka, severity) rows out of the text of an official drought order.

If the order has an annex table (a serial-number header "अ.क्र." ... a total line "एकूण"), only that table is read:
the letterhead and prose never produce talukas, and row lines ("18 बीड परळी, आष्टी") are split into single names.
Otherwise lines are scanned in order: a line naming a district ("जिल्हा : सोलापूर" / "District: Solapur") sets the district
for the lines below it; every other name-like piece of text is matched against that district's talukas.
Severity comes from the English translation of the line (IndicTrans2), else from the order's title, else it is
left "unknown" for a person to fill in.
"""
import re
from dataclasses import dataclass, field, replace
from datetime import date

from app.domain.declarations import REVIEW_FROM, TalukaMatcher, severity_from_text
from app.integrations.ports import Translator

_NUMBER = re.compile(r"[०-९0-9]+[.)]?")  # serial numbers and counts: the cell breaks of a table row
_SPLIT = re.compile(r"[,|;:\t()\[\]]|\s{2,}|[०-९0-9]+[.)]?")
# also the forms broken PDF fonts produce (जिल्हा -> जजल्हा, see app/domain/declarations.pdf_repairs)
_DISTRICT_WORDS = re.compile(r"(जिल्हा|जजल्हा|जिल्ह्यातील|जजल्ह्यातील|जिल्ह्याती|district)", re.I)
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_TABLE_START = re.compile(r"अ\.\s*क्र|\bS(?:r|l)?\.?\s*No\b", re.I)  # serial-number column header
_TABLE_END = re.compile(r"एकूण|एकूर्|एकुण|^\s*total\b", re.I)  # the table's total line
# lines inside the table that hold no talukas: column titles, the header repeated on every page, "निरंक" (none)
_TABLE_HEADER = re.compile(r"नावे|नािे|सांख्या|संख्या|names|number|शासन|हंगाम|हांगाम|trigger|पृष्ठ|परिशिष्ट|पनिनशष्ट"
                           r"|अ\.\s*क्र|निरंक|\bnil\b", re.I)


@dataclass
class Extraction:
    accepted: list[dict] = field(default_factory=list)
    check: list[dict] = field(default_factory=list)


class DeclarationExtractor:
    TITLE_LINES = 3  # fallback title length when the order has no district headings

    def __init__(self, matcher: TalukaMatcher, translator: Translator | None = None):
        self.matcher = matcher
        self.translator = translator
        self.districts = sorted({d for _, _, d in matcher.talukas_raw if d})

    def extract(self, lines: list[str], *, state_code: str, declared_on: date, order_ref: str | None,
                source_url: str | None, src_lang: str = "mr") -> Extraction:
        lines = [ln.strip() for ln in lines if ln.strip()]
        table = self._table_region(lines)
        if table is not None:
            return self._extract_table(lines, table, state_code=state_code, declared_on=declared_on,
                                       order_ref=order_ref, source_url=source_url, src_lang=src_lang)
        english = self._translate(lines, src_lang)
        # the order's title is everything before its first district heading; a severity stated there covers
        # the whole order, while a severity on a list line covers that line only
        first_heading = next((i for i, (ln, en) in enumerate(zip(lines, english))
                              if _DISTRICT_WORDS.search(ln) or _DISTRICT_WORDS.search(en)), self.TITLE_LINES)
        title_severity = (severity_from_text(" ".join(english[:first_heading]))
                          or severity_from_text(" ".join(lines[:first_heading])))
        out = Extraction()
        seen: set[int] = set()
        district: str | None = None
        for line, line_en in zip(lines, english):
            if _DISTRICT_WORDS.search(line) or _DISTRICT_WORDS.search(line_en):
                district = self._district_in(line) or district
                continue
            severity = severity_from_text(line_en) or severity_from_text(line) or title_severity or "unknown"
            for piece in (p.strip(" .-–") for p in _SPLIT.split(line)):
                if len(piece) < 3:
                    continue
                hit = self.matcher.match(piece, district=district)
                if hit is None or hit.score < REVIEW_FROM:
                    continue
                row = {"state_code": state_code, "district": hit.district, "taluka": hit.name, "area_id": hit.area_id,
                       "declared_on": declared_on.isoformat(), "severity": severity, "order_ref": order_ref,
                       "source_url": source_url, "confidence": round(hit.score, 1), "source_text": piece}
                if hit.score >= TalukaMatcher.ACCEPT and hit.area_id not in seen:
                    seen.add(hit.area_id)
                    out.accepted.append(row)
                elif hit.score < TalukaMatcher.ACCEPT:
                    out.check.append(row)
        return out

    @staticmethod
    def _table_region(lines: list[str]) -> tuple[int, int] | None:
        start = next((i for i, ln in enumerate(lines) if _TABLE_START.search(ln)), None)
        if start is None:
            return None
        end = next((i for i in range(start + 1, len(lines)) if _TABLE_END.search(lines[i])), len(lines))
        return start + 1, end

    def _extract_table(self, lines: list[str], region: tuple[int, int], *, state_code: str, declared_on: date,
                       order_ref: str | None, source_url: str | None, src_lang: str) -> Extraction:
        start, end = region
        title = lines[:start - 1]
        title_severity = (severity_from_text(" ".join(self._translate(title, src_lang)))
                          or severity_from_text(" ".join(title)))
        rows = [ln for ln in lines[start:end] if not _TABLE_HEADER.search(ln)]
        # the district and revenue-division columns come first in a cell ("6 नाशिक 10", a lone "ठाणे", "18 बीड परळी,");
        # a taluka named like a district found there is that column, not a declared taluka: a person checks it
        district_keys = {t[4] for t in self.matcher.talukas}
        namesakes = {t[0] for t in self.matcher.talukas if t[3] & district_keys}
        found = []  # (line number, hit, text, severity, is a district name in the district column)
        for i, line in enumerate(rows):
            severity = severity_from_text(line) or title_severity or "unknown"
            for cell in _NUMBER.split(line):
                pieces = [p.strip(" .-–") for p in _SPLIT.split(cell)]
                listed = len(pieces) > 1
                for n, piece in enumerate(pieces):
                    first = piece.split()[0] if n == 0 and piece else None
                    for hit, text in self._names_in(piece):
                        column = text == first and not (listed and text == piece)
                        if column:
                            first = None  # only its first word is the column ("रत्नागिरी रत्नागिरी," = district, taluka)
                            if self._district_in(text):
                                continue  # the district / division column itself: not a taluka, nothing to check
                        column = column and hit.area_id in namesakes
                        if column:
                            hit = replace(hit, score=min(hit.score, TalukaMatcher.ACCEPT - 1))
                        found.append((i, hit, text, severity, column))
        out, seen = Extraction(), set[int]()
        for i, hit, text, severity, column in found:
            if hit.score < TalukaMatcher.ACCEPT and not column:
                hit = self._settle_by_neighbours(text, i, found) or hit
            self._add(out, seen, hit, text, severity, state_code, declared_on, order_ref, source_url)
        out.check = [r for r in out.check if r["area_id"] not in seen]  # already accepted from another line
        return out

    NEIGHBOURS = 2  # a table row's names spread over a few lines above and below its serial number

    def _settle_by_neighbours(self, text: str, line: int, found: list):
        """A name found in two districts (Malegaon: Nashik and Washim) is the one in the district of the names
        accepted around it, when exactly one of its districts is there."""
        near = {h.district for i, h, *_ in found if abs(i - line) <= self.NEIGHBOURS and h.score >= TalukaMatcher.ACCEPT}
        hits = [self.matcher.match(text, district=d) for d in near if d]
        good = {h.area_id: h for h in hits if h is not None and h.score >= TalukaMatcher.ACCEPT}
        return next(iter(good.values())) if len(good) == 1 else None

    def _names_in(self, piece: str) -> list[tuple]:
        """A table cell piece is one name, or a district and a name written together ("बीड परळी")."""
        if len(piece) < 2:
            return []
        whole = self.matcher.match(piece)
        if whole is not None and whole.score >= TalukaMatcher.ACCEPT:
            return [(whole, piece)]
        # a word ending in ् is half of a name the PDF split ("अनहल् यािगर"), except a broken र् (see pdf_repairs)
        words = [w for w in piece.split() if len(w) >= 2 and not (w.endswith("्") and not w.endswith("र्"))]
        hits = [(self.matcher.match(w), w) for w in words] if len(words) > 1 else []
        hits = [(h, w) for h, w in hits if h is not None and h.score >= REVIEW_FROM]
        if hits:
            return hits
        return [(whole, piece)] if whole is not None and whole.score >= REVIEW_FROM else []

    @staticmethod
    def _add(out: Extraction, seen: set, hit, text: str, severity: str, state_code: str, declared_on: date,
             order_ref: str | None, source_url: str | None) -> None:
        row = {"state_code": state_code, "district": hit.district, "taluka": hit.name, "area_id": hit.area_id,
               "declared_on": declared_on.isoformat(), "severity": severity, "order_ref": order_ref,
               "source_url": source_url, "confidence": round(hit.score, 1), "source_text": text}
        if hit.score >= TalukaMatcher.ACCEPT:
            if hit.area_id not in seen:
                seen.add(hit.area_id)
                out.accepted.append(row)
        else:
            out.check.append(row)

    def _district_in(self, line: str) -> str | None:
        pieces = [p.strip(" .-–") for p in _SPLIT.split(_DISTRICT_WORDS.sub(" ", line)) if len(p.strip()) >= 3]
        best = None
        for piece in pieces:
            for d in self.districts:
                score = TalukaMatcher([(0, d, d)]).match(piece)
                if score and score.score >= 85 and (best is None or score.score > best[1]):
                    best = (d, score.score)
        return best[0] if best else None

    def _translate(self, lines: list[str], src_lang: str) -> list[str]:
        if self.translator is None:
            return ["" for _ in lines]
        indic = [i for i, ln in enumerate(lines) if _DEVANAGARI.search(ln)]
        translated = self.translator.translate([lines[i] for i in indic], src_lang) if indic else []
        english = list(lines)  # English lines stay as they are (Karnataka press lists)
        for i, text in zip(indic, translated):
            english[i] = text
        return english
