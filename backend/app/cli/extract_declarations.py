"""Extract official drought declarations (taluka lists) from a state order into a CSV for review and loading.

Usage (from backend/):
  uv run python -m app.cli.extract_declarations --pdf GR.pdf --state MH --date 2026-09-25 \
      --order-ref "GR 25 Sep 2026" --url https://gr.maharashtra.gov.in/...
  uv run python -m app.cli.extract_declarations --text karnataka_list.txt --state KA --date 2026-10-02 --lang en

Writes app/data/declarations/<state>_<date>.csv (accepted rows) and ..._check.csv (rows a person must confirm).
Then load with: uv run python -m app.cli.load_declarations <csv>.
Marathi severity words are translated locally with IndicTrans2 when installed (`uv sync --extra indic`) and
HF_TOKEN is set; without it, names still match and severity is marked "unknown" for you to fill in.
"""
import argparse
import csv
import logging
from datetime import date
from pathlib import Path

from app.core.config import settings
from app.core.database import init_db, session_scope
from app.core.exceptions import ExternalServiceError
from app.domain.declarations import TalukaMatcher
from app.integrations.pdf_text import pdf_lines
from app.repositories.admin_area_repository import AdminAreaRepository
from app.services.declaration_extractor import DeclarationExtractor, Extraction

LOG = logging.getLogger(__name__)
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "declarations"
COLUMNS = ["state_code", "district", "taluka", "area_id", "declared_on", "severity", "order_ref", "source_url",
           "confidence", "source_text"]


def write(result: Extraction, out: Path) -> tuple[Path, Path]:
    out.parent.mkdir(parents=True, exist_ok=True)
    check = out.with_name(out.stem + "_check.csv")
    for path, rows in ((out, result.accepted), (check, result.check)):
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
    return out, check


def run(lines: list[str], talukas, *, state: str, day: date, order_ref: str | None, url: str | None, lang: str,
        translate: bool, out: Path) -> Extraction:
    translator = None
    if translate and lang != "en":
        from app.integrations.indictrans import IndicTranslator
        translator = IndicTranslator(settings.hf_token)
    extractor = DeclarationExtractor(TalukaMatcher(talukas), translator)
    try:
        result = extractor.extract(lines, state_code=state, declared_on=day, order_ref=order_ref, source_url=url,
                                   src_lang=lang)
    except ExternalServiceError as exc:  # model not installed / gated: keep going without translation
        print(f"translation unavailable ({exc}); severity will be 'unknown' where the order states it in words")
        result = DeclarationExtractor(TalukaMatcher(talukas), None).extract(
            lines, state_code=state, declared_on=day, order_ref=order_ref, source_url=url, src_lang=lang)
    write(result, out)
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf", type=Path)
    src.add_argument("--text", type=Path, help="plain-text list (e.g. names copied from a press release)")
    p.add_argument("--state", required=True, help="state code, e.g. MH or KA")
    p.add_argument("--date", required=True, type=date.fromisoformat, help="date of the order (YYYY-MM-DD)")
    p.add_argument("--order-ref")
    p.add_argument("--url")
    p.add_argument("--lang", default="mr", help="mr (Marathi), hi, kn, ... or en")
    p.add_argument("--no-translate", action="store_true")
    args = p.parse_args()

    lines = pdf_lines(args.pdf, args.lang) if args.pdf else args.text.read_text(encoding="utf-8").splitlines()
    init_db()
    with session_scope() as session:
        talukas = AdminAreaRepository(session).talukas(args.state)
    if not talukas:
        raise SystemExit(f"no talukas loaded for {args.state}: run app.cli.seed_geo first")
    out = OUT_DIR / f"{args.state}_{args.date.isoformat()}.csv"
    result = run(lines, talukas, state=args.state, day=args.date, order_ref=args.order_ref, url=args.url,
                 lang=args.lang, translate=not args.no_translate, out=out)
    print(f"accepted {len(result.accepted)} talukas -> {out}")
    print(f"needs your check: {len(result.check)} -> {out.with_name(out.stem + '_check.csv')}")


if __name__ == "__main__":
    main()
