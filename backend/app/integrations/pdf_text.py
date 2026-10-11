"""Text out of PDF orders: pdfplumber first; pages typed in old fonts (garbled text) go to local OCR when installed."""
import logging
from pathlib import Path
from typing import BinaryIO

from app.domain.declarations import looks_garbled

LOG = logging.getLogger(__name__)


def pdf_lines(path: Path | BinaryIO, lang: str) -> list[str]:
    """Text lines of a PDF (a path, or bytes in a file-like object). Pages typed in old fonts (garbled text) are read with local OCR when available."""
    import pdfplumber

    lines: list[str] = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if looks_garbled(text) or not text.strip():
                text = _ocr(page, lang) or text
                if looks_garbled(text):
                    LOG.warning("page %d: text is garbled and OCR is unavailable; skipped", number)
                    continue
            lines += text.splitlines()
    return lines


def _ocr(page, lang: str) -> str | None:
    try:
        import pytesseract
        image = page.to_image(resolution=300).original
        return pytesseract.image_to_string(image, lang={"mr": "mar", "hi": "hin", "kn": "kan"}.get(lang, "eng"))
    except Exception as exc:  # noqa: BLE001 - OCR is optional (needs the Tesseract program + language data)
        LOG.warning("OCR unavailable (%s): install Tesseract with the Marathi language pack", type(exc).__name__)
        return None
