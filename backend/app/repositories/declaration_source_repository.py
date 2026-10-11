from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.models import DeclarationMention, DeclarationSource
from app.repositories.base import BaseRepository


class DeclarationSourceRepository(BaseRepository[DeclarationSource]):
    """News articles / official PDFs read by the declaration watch, and the talukas each one named."""

    model = DeclarationSource
    MAX_ATTEMPTS = 2  # a failed download is tried once more on the next run, then left alone

    def get_by_url(self, url: str) -> DeclarationSource | None:
        return self.session.scalar(select(DeclarationSource).where(DeclarationSource.url == url))

    def save(self, source: DeclarationSource) -> DeclarationSource:
        self.session.add(source)
        self.session.flush()
        return source

    def retryable(self) -> list[DeclarationSource]:
        return list(self.session.scalars(select(DeclarationSource).where(
            DeclarationSource.status == "failed", DeclarationSource.attempts < self.MAX_ATTEMPTS)))

    def add_mentions(self, source_id: int, rows: list[dict]) -> None:
        if rows:
            self.session.execute(insert(DeclarationMention).values([{**r, "source_id": source_id} for r in rows])
                                 .on_conflict_do_nothing(index_elements=["source_id", "area_id"]))
            self.session.flush()

    def mentions(self, since: date, min_score: float = 0.0) -> list[tuple[DeclarationMention, DeclarationSource]]:
        """Mentions from listed sources published on or after `since`, scoring at least `min_score`."""
        query = (select(DeclarationMention, DeclarationSource)
                 .join(DeclarationSource, DeclarationSource.id == DeclarationMention.source_id)
                 .where(DeclarationSource.status == "listed", DeclarationSource.published_on >= since,
                        DeclarationMention.score >= min_score)
                 .order_by(DeclarationSource.published_on, DeclarationSource.id))
        return [(m, s) for m, s in self.session.execute(query).all()]

    def status_counts(self, since: date) -> dict[str, int]:
        query = (select(DeclarationSource.status, func.count()).where(DeclarationSource.published_on >= since)
                 .group_by(DeclarationSource.status))
        return {status: n for status, n in self.session.execute(query).all()}

    def last_checked(self):
        return self.session.scalar(select(func.max(DeclarationSource.checked_at)))
