"""Daily watch for state drought declarations in the news: search -> read each new article (and any official PDF it
links) -> keep only sentences that declare -> find the state -> store which source named which taluka.

Nothing here declares a taluka; DeclarationPromoter applies the safety rule (1 official order or 2 independent news
sites) to the stored mentions.
"""
import io
import logging
import re
from collections.abc import Callable
from datetime import date, datetime
from urllib.parse import urlsplit

import trafilatura

from app.domain.declaration_states import WATCH_STATES, declares, list_sentences, order_dates, pick_state
from app.domain.declarations import REVIEW_FROM, TalukaMatcher, severity_from_text
from app.domain.text import TextFingerprinter
from app.integrations.declaration_news import FetchBlocked, FetchFailed
from app.integrations.pdf_text import pdf_lines
from app.models import DeclarationSource
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.declaration_source_repository import DeclarationSourceRepository

LOG = logging.getLogger(__name__)
_PDF_LINK = re.compile(r"""href=["'](https?://[^"'\s]+?\.pdf)["']""", re.I)
_GOVERNMENT_HOST = re.compile(r"(?:^|\.)(?:gov|nic)\.in$", re.I)


def official_links(page: str) -> list[str]:
    """PDF links in an article that are hosted on a government site (.gov.in / .nic.in); a government address
    inside another site's link (web.archive.org/..., evil.test/x.gov.in/...) does not count."""
    return list(dict.fromkeys(u for u in _PDF_LINK.findall(page)
                              if _GOVERNMENT_HOST.search(urlsplit(u).hostname or "")))


def html_text(body: bytes) -> str:
    return trafilatura.extract(body.decode("utf-8", "replace")) or ""


def pdf_text(body: bytes) -> list[str]:
    return pdf_lines(io.BytesIO(body), "en")


class DeclarationWatchService:
    def __init__(self, search, fetcher, sources: DeclarationSourceRepository, areas: AdminAreaRepository,
                 fingerprinter: TextFingerprinter, html_text: Callable[[bytes], str] = html_text,
                 pdf_text: Callable[[bytes], list[str]] = pdf_text):
        self.search = search
        self.fetcher = fetcher
        self.sources = sources
        self.areas = areas
        self.fingerprinter = fingerprinter
        self.html_text = html_text
        self.pdf_text = pdf_text
        self._matchers: dict[str, TalukaMatcher] = {}

    def run(self, now: datetime) -> dict:
        hits = self.search.search()  # a GDELT failure stops this run only; the stage records it
        queue: list[tuple[str, str, str | None, date]] = [(h.url, "news", h.title, h.published_on) for h in hits]
        queue += [(s.url, s.kind, s.title, s.published_on) for s in self.sources.retryable()]
        stats: dict = {"hits": len(hits), "new": 0, "listed": 0, "mentions": 0, "by_status": {}}
        done: set[str] = set()
        while queue:
            url, kind, title, published_on = queue.pop(0)
            existing = self.sources.get_by_url(url)
            if url in done or (existing is not None and not self._retry(existing)):
                continue
            done.add(url)
            stats["new"] += existing is None
            source, links, mentions = self._read(url, kind, title, published_on, now, existing)
            queue += [(link, "official", title, published_on) for link in links]
            stats["by_status"][source.status] = stats["by_status"].get(source.status, 0) + 1
            stats["listed"] += source.status == "listed"
            stats["mentions"] += mentions
        return stats

    def _retry(self, source: DeclarationSource) -> bool:
        return source.status == "failed" and source.attempts < self.sources.MAX_ATTEMPTS

    def _read(self, url: str, kind: str, title: str | None, published_on: date, now: datetime,
              existing: DeclarationSource | None) -> tuple[DeclarationSource, list[str], int]:
        source = existing or DeclarationSource(url=url, domain=urlsplit(url).hostname or "", kind=kind, title=title,
                                               published_on=published_on, attempts=0)
        source.attempts = (source.attempts or 0) + 1
        source.checked_at = now
        links: list[str] = []
        rows: list[dict] = []
        try:
            fetched = self.fetcher.get(url, expect_pdf=kind == "official")
        except FetchBlocked:
            source.status = "blocked"
        except FetchFailed as exc:
            LOG.info("declaration source failed: %s", exc)
            source.status = "failed"
        except Exception:  # noqa: BLE001 - one odd page (bad URL, ...) never stops the others
            LOG.exception("declaration source failed: %s", url)
            source.status = "failed"
        else:
            try:
                links, rows = self._understand(source, fetched.body, now)
            except Exception:  # noqa: BLE001 - a broken / truncated file fails only itself
                LOG.exception("could not read declaration source %s", url)
                source.status, links, rows = "failed", [], []
        self.sources.save(source)
        self.sources.add_mentions(source.id, rows)
        return source, links, len(rows)

    def _understand(self, source: DeclarationSource, body: bytes, now: datetime) -> tuple[list[str], list[dict]]:
        links: list[str] = []
        if source.kind == "official":
            text = "\n".join(self.pdf_text(body))
            # an order is dated by its own text: a 2023 order linked from a 2026 article stays a 2023 order; with no
            # date in it, it counts only like one news source (never declares alone)
            dates = [d for d in order_dates(text) if d <= now.date()]
            if dates:
                source.published_on = dates[-1]
            else:
                source.kind = "news"
        else:
            text = self.html_text(body)
            links = official_links(body.decode("utf-8", "replace"))
        source.status, source.state_code, source.list_fingerprint, rows = self._mentions(f"{source.title or ''}\n{text}")
        return links, rows

    def _mentions(self, text: str) -> tuple[str, str | None, int | None, list[dict]]:
        sentences = list_sentences(text)
        if not sentences:
            return ("no_list" if declares(text) else "not_declaration"), None, None, []
        items = [(s, name) for s in sentences for name in s.names]
        counts, hits = {}, {}
        for pool in {s.pool for s in WATCH_STATES}:
            matcher = self._matcher(pool)
            hits[pool] = [(s, name, matcher.match(name)) for s, name in items]
            accepted = len({h.area_id for *_, h in hits[pool] if h is not None and h.score >= TalukaMatcher.ACCEPT})
            if accepted:
                counts[pool] = (accepted, len(items))
        state = pick_state(counts, text)
        if state is None:
            return "state_unclear", None, None, []
        rows = [{"area_id": h.area_id, "score": round(h.score, 1), "text": name,
                 "severity": severity_from_text(s.text)}
                for s, name, h in hits[state.pool] if h is not None and h.score >= REVIEW_FROM]
        fingerprint = self.fingerprinter.simhash(" ".join(s.text for s in sentences))
        return "listed", state.pool, fingerprint, rows

    def _matcher(self, pool: str) -> TalukaMatcher:
        if pool not in self._matchers:
            self._matchers[pool] = TalukaMatcher(self.areas.talukas(pool))
        return self._matchers[pool]
