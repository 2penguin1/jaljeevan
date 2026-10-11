"""The safety rule for news-based declarations: a taluka is declared when, within one season (120 days), it is named
by one official order, or by two independent news sources: different websites whose list sentences are not the same
wire copy (simhash). A taluka that already has a declaration this season (any route, e.g. the Maharashtra GR) is never
rewritten.
"""
from collections import defaultdict
from datetime import datetime, timedelta

from app.domain.declarations import REVIEW_FROM, TalukaMatcher
from app.domain.text import TextFingerprinter
from app.models import DeclarationMention, DeclarationSource
from app.repositories.declaration_repository import DeclarationRepository
from app.repositories.declaration_source_repository import DeclarationSourceRepository

SEASON = timedelta(days=120)
NEWS_SOURCES_NEEDED = 2


class DeclarationPromoter:
    def __init__(self, sources: DeclarationSourceRepository, declarations: DeclarationRepository,
                 fingerprinter: TextFingerprinter):
        self.sources = sources
        self.declarations = declarations
        self.fingerprinter = fingerprinter

    def promote(self, now: datetime) -> dict:
        since = now.date() - SEASON
        by_area: dict[tuple[str, int], list[tuple[DeclarationMention, DeclarationSource]]] = defaultdict(list)
        for mention, source in self.sources.mentions(since, min_score=TalukaMatcher.ACCEPT):
            by_area[(source.state_code, mention.area_id)].append((mention, source))
        already = self.declarations.active(since)
        declared: dict[str, int] = defaultdict(int)
        waiting = 0
        for (state, area_id), rows in by_area.items():
            if area_id in already:
                continue
            officials = [s for _, s in rows if s.kind == "official"]
            news = self.independent([s for _, s in rows if s.kind == "news"])
            if not officials and len(news) < NEWS_SOURCES_NEEDED:
                waiting += 1
                continue
            counting = officials or news  # an official order speaks for itself: its own date, its own words
            ids = {s.id for s in counting}
            severities = {m.severity for m, s in rows if m.severity and s.id in ids}
            severity = "severe" if "severe" in severities else "moderate"
            ref = "official order" if officials else f"news: {len(news)} sources"
            if not severities:
                ref += " (severity not stated)"
            first = min(counting, key=lambda s: (s.published_on, s.id))
            self.declarations.upsert(area_id, state, first.published_on, severity, ref, first.url)
            declared[state] += 1
        return {"declared": dict(declared), "waiting": waiting}

    def pending(self, now: datetime) -> list[tuple[DeclarationMention, DeclarationSource, int]]:
        """Talukas named this season but not declared (one source only, or a doubtful match), for a person to check:
        (best mention, its source, number of independent sources)."""
        since = now.date() - SEASON
        already = self.declarations.active(since)
        by_area: dict[int, list[tuple[DeclarationMention, DeclarationSource]]] = defaultdict(list)
        for mention, source in self.sources.mentions(since, min_score=REVIEW_FROM):
            if mention.area_id not in already:
                by_area[mention.area_id].append((mention, source))
        out = []
        for rows in by_area.values():
            mention, source = max(rows, key=lambda r: (r[0].score, -r[1].id))
            out.append((mention, source, len(self.independent([s for _, s in rows if s.kind == "news"]))))
        return out

    def independent(self, news: list[DeclarationSource]) -> list[DeclarationSource]:
        """Earliest first; a source counts only if its website and its list text are new (wire copies are one)."""
        kept: list[DeclarationSource] = []
        for source in sorted(news, key=lambda s: (s.published_on, s.id)):
            if any(_site(source.domain) == _site(k.domain) for k in kept):
                continue
            if any(source.list_fingerprint is not None and k.list_fingerprint is not None
                   and self.fingerprinter.is_near_duplicate(source.list_fingerprint, k.list_fingerprint)
                   for k in kept):
                continue
            kept.append(source)
        return kept


_SECOND_LEVEL = {"co", "gov", "nic", "org", "net", "ac", "edu", "res", "gen", "firm", "ind"}  # x.co.in, x.gov.in


def _site(domain: str) -> str:
    """The publisher behind a host: www.news18.com, kannada.news18.com and m.news18.com are one website."""
    labels = (domain or "").lower().rstrip(".").split(".")
    keep = 3 if len(labels) >= 3 and labels[-1] == "in" and labels[-2] in _SECOND_LEVEL else 2
    return ".".join(labels[-keep:])
