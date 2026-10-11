"""Turns official order PDFs dropped into a folder into declaration CSVs, then files them away.

Drop a PDF in app/data/declarations/inbox/ (e.g. downloaded with scripts/fetch_gr_pdfs.py). Each run reads the new
files once: drought orders become <state>_<order>.csv (accepted) + _check.csv (for a person), anything else is set
aside. Maharashtra file names are the official GR number, which starts with the order's date (YYYYMMDD...).
"""
import csv
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from app.domain.declarations import TalukaMatcher
from app.integrations.ports import Translator
from app.services.declaration_extractor import DeclarationExtractor

_GR_CODE = re.compile(r"^(\d{8})\d{6,}$")
# a declaration says so: "दुष्काळ जाहीर" / "declared drought-hit"; orders that only discuss drought (a review
# committee, relief funds) must never load talukas
_DROUGHT = r"(?:दुष्काळ|दुष्काल|सूखा|drought|scarcity)"
_DECLARED = r"(?:जाहीर|घोषित|declar\w*)"
_DECLARATION = re.compile(f"{_DROUGHT}.{{0,60}}?{_DECLARED}|{_DECLARED}.{{0,60}}?{_DROUGHT}", re.I | re.S)
COLUMNS = ["state_code", "district", "taluka", "area_id", "declared_on", "severity", "order_ref", "source_url",
           "confidence", "source_text"]


def order_from_filename(name: str) -> tuple[date, str] | None:
    """'202609251512341234.pdf' -> (2026-09-25, 'GR 202609251512341234'); None for other names."""
    stem = Path(name).stem
    m = _GR_CODE.match(stem)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d").date(), f"GR {stem}"
    except ValueError:
        return None


@dataclass
class InboxResult:
    file: str
    status: str            # extracted | not a drought declaration | unreadable
    declared_on: date | None = None
    order_ref: str | None = None
    accepted: int = 0
    to_check: int = 0
    csv: Path | None = None


class DeclarationInbox:
    def __init__(self, inbox: Path, out_dir: Path, read_lines: Callable[[Path], list[str]],
                 talukas_for: Callable[[str], list[tuple[int, str, str | None]]], translator: Translator | None = None):
        self.inbox = Path(inbox)
        self.out_dir = Path(out_dir)
        self.read_lines = read_lines
        self.talukas_for = talukas_for
        self.translator = translator

    def process(self, state: str = "MH") -> list[InboxResult]:
        results = []
        for pdf in sorted(self.inbox.glob("*.pdf")):
            results.append(self._one(pdf, state))
        return results

    def _one(self, pdf: Path, state: str) -> InboxResult:
        parsed = order_from_filename(pdf.name)
        if parsed:
            declared_on, ref = parsed
        else:  # hand-named file: the day it was saved is the best date we have, and the CSV says so
            declared_on = date.fromtimestamp(pdf.stat().st_mtime)
            ref = f"{pdf.name} (date from file)"
        try:
            lines = self.read_lines(pdf)
        except Exception:  # noqa: BLE001 - a broken PDF is set aside, never stops the other files
            self._move(pdf, "skipped")
            return InboxResult(pdf.name, "unreadable", declared_on, ref)
        if not _DECLARATION.search(" ".join(lines)):
            self._move(pdf, "skipped")
            return InboxResult(pdf.name, "not a drought declaration", declared_on, ref)
        extraction = DeclarationExtractor(TalukaMatcher(self.talukas_for(state)), self.translator).extract(
            lines, state_code=state, declared_on=declared_on, order_ref=ref, source_url=None)
        out = self.out_dir / f"{state}_{Path(pdf.name).stem}.csv"
        self._write(out, extraction.accepted)
        self._write(out.with_name(out.stem + "_check.csv"), extraction.check)
        self._move(pdf, "processed")
        return InboxResult(pdf.name, "extracted", declared_on, ref, len(extraction.accepted), len(extraction.check), out)

    def _move(self, pdf: Path, folder: str) -> None:
        target = self.inbox / folder
        target.mkdir(exist_ok=True)
        shutil.move(str(pdf), str(target / pdf.name))

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
