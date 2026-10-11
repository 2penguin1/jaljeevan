"""Pulls (district, taluka, severity) rows out of the text of an official drought order.

Lines are scanned in order: a line naming a district ("जिल्हा : सोलापूर" / "District: Solapur") sets the district
for the lines below it; every other name-like piece of text is matched against that district's talukas.
Severity comes from the English translation of the line (IndicTrans2), else from the order's title, else it is
left "unknown" for a person to fill in.
"""
import re
from dataclasses import dataclass, field
from datetime import date

from app.domain.declarations import TalukaMatcher, severity_from_text
from app.integrations.ports import Translator

_SPLIT = re.compile(r"[,|;:\t()\[\]]|\s{2,}|[०-९0-9]+[.)]?")
# also the forms broken PDF fonts produce (जिल्हा -> जजल्हा, see app/domain/declarations.pdf_repairs)
_DISTRICT_WORDS = re.compile(r"(जिल्हा|जजल्हा|जिल्ह्यातील|जजल्ह्यातील|जिल्ह्याती|district)", re.I)
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
REVIEW_FROM = 70.0  # scores between this and TalukaMatcher.ACCEPT go to the "check me" list


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
