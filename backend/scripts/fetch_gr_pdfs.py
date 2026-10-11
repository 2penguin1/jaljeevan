"""TEMPORARY helper: download past Maharashtra drought orders (Government Resolutions) into the declarations inbox.

The GR search is protected by a captcha, and this script does NOT get around it: it opens a normal, visible browser,
fills in the search (Relief & Rehabilitation department + keyword), and **you** type the captcha and press Search.
It then reads every result and downloads each official PDF.

First time only:  cd backend && uv run playwright install chromium
Run:              cd backend && uv run python -m scripts.fetch_gr_pdfs [--keyword दुष्काळ]
Then:             uv run python -m app.cli.process_declaration_inbox
Delete this file once past orders are in; new orders are picked up from the open "latest orders" page.
"""
import argparse
import html
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

URL = "https://gr.maharashtra.gov.in/1145/Government-Resolutions"
RELIEF_DEPARTMENT = "41"  # मदत व पुनर्वसन विभाग (Relief and Rehabilitation), the department that declares drought
INBOX = Path(__file__).resolve().parents[1] / "app" / "data" / "declarations" / "inbox"

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_PDF = re.compile(r'href="([^"]+\.pdf)"')


@dataclass(frozen=True)
class GrRow:
    code: str
    day: date
    title: str
    url: str


def parse_results(page_html: str) -> list[GrRow]:
    """Rows of the results grid: (GR code, date, title, absolute PDF link)."""
    out = []
    for row in _ROW.findall(page_html):
        link = _PDF.search(row)
        cells = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split()) for c in _CELL.findall(row)]
        if not link or len(cells) < 5:
            continue
        try:
            day = datetime.strptime(cells[4], "%d-%m-%Y").date()
        except ValueError:
            continue
        out.append(GrRow(cells[3], day, cells[2], urljoin(URL, link.group(1))))
    return out


def read_page(page, attempts: int = 6, sleep=time.sleep) -> str:
    """The page's HTML once it has stopped loading. The site reloads itself after a search (and after its own
    pop-up messages), so reading can briefly fail mid-navigation: wait and try again instead of crashing."""
    last: Exception | None = None
    for _ in range(attempts):
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:  # noqa: BLE001 - a slow page is retried below
            pass
        try:
            return page.content()
        except Exception as exc:  # noqa: BLE001 - "page is navigating": retry
            last = exc
            sleep(1.0)
    raise last if last else RuntimeError("page could not be read")


def main() -> None:
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--keyword", default="दुष्काळ", help="search keyword (default: दुष्काळ = drought)")
    parser.add_argument("--max-pages", type=int, default=10)
    args = parser.parse_args()
    INBOX.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        def on_dialog(dialog):  # the site's own pop-ups (e.g. a wrong captcha): show the text here and close it
            print(f"\n  [site message] {dialog.message}")
            dialog.accept()

        page.on("dialog", on_dialog)
        page.goto(URL)
        page.select_option("#SitePH_ddlDepartmentType", RELIEF_DEPARTMENT)
        page.wait_for_load_state("networkidle")
        page.fill("#SitePH_txtKeywords", args.keyword)
        rows: list[GrRow] = []
        while not rows:
            print("\nIn the browser window: type the captcha and click 'शोधा' (Search).")
            answer = input("When the results are showing, press Enter here (or type q to quit)... ")
            if answer.strip().lower() == "q":
                browser.close()
                return
            rows = parse_results(read_page(page))
            if not rows:
                print("  No results on the page yet (wrong captcha, or still loading). Try the search again.")

        saved, seen = 0, set()
        for page_no in range(1, args.max_pages + 1):
            rows = [r for r in parse_results(read_page(page)) if r.code not in seen]
            if not rows:
                break
            for r in rows:
                seen.add(r.code)
                target = INBOX / f"{r.code}.pdf"
                if target.exists():
                    continue
                response = page.request.get(r.url)  # same browser session as the search you made
                if response.ok and response.body()[:4] == b"%PDF":
                    target.write_bytes(response.body())
                    saved += 1
                    print(f"  saved {r.day} {r.code}  {r.title[:70]}")
                else:
                    print(f"  could not download {r.code} (HTTP {response.status})")
            next_link = page.locator(f"#SitePH_ucPaging_p{page_no + 1}")
            if next_link.count() == 0:
                break
            next_link.first.click()
            read_page(page)  # let the next page finish loading
        print(f"\n{saved} new PDF(s) in {INBOX}")
        print("Next: uv run python -m app.cli.process_declaration_inbox")
        browser.close()


if __name__ == "__main__":
    main()
