"""Process official drought-order PDFs dropped into app/data/declarations/inbox/ and load them.

Usage (from backend/): uv run python -m app.cli.process_declaration_inbox [--state MH]
Writes <state>_<order>.csv (loaded automatically) and <state>_<order>_check.csv (rows for you to confirm, then load
with app.cli.load_declarations). Processed files move to inbox/processed/, non-drought ones to inbox/skipped/.
"""
import argparse
from pathlib import Path

from sqlalchemy.orm import Session

from app.cli.extract_declarations import pdf_lines
from app.cli.load_declarations import load_csv
from app.core.config import settings
from app.core.database import init_db, session_scope
from app.repositories.admin_area_repository import AdminAreaRepository
from app.services.declaration_inbox import DeclarationInbox

DATA = Path(__file__).resolve().parents[1] / "data" / "declarations"


def _translator():
    """Local IndicTrans2 when installed and unlocked; otherwise names still match and severity stays 'unknown'."""
    if not settings.hf_token:
        return None
    try:
        import transformers  # noqa: F401
    except ImportError:
        return None
    from app.integrations.indictrans import IndicTranslator
    return IndicTranslator(settings.hf_token)


def run(session: Session, inbox: Path, out_dir: Path, read_lines=None, translator=None, state: str = "MH") -> int:
    areas = AdminAreaRepository(session)
    box = DeclarationInbox(inbox, out_dir, read_lines or (lambda p: pdf_lines(p, "mr")), areas.talukas, translator)
    loaded = 0
    for result in box.process(state):
        line = f"{result.file}: {result.status}"
        if result.status == "extracted":
            count, skipped = load_csv(session, result.csv)
            loaded += count
            line += f" - {count} talukas loaded, {result.to_check} to check ({result.csv.name})"
        print(line)
    return loaded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", default="MH")
    args = parser.parse_args()
    init_db()
    inbox = DATA / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    with session_scope() as session:
        total = run(session, inbox, DATA, translator=_translator(), state=args.state)
    print(f"done: {total} declarations loaded")


if __name__ == "__main__":
    main()
