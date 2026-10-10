from sqlalchemy import select

from app.models import SourceDomain
from app.repositories.base import BaseRepository


class SourceDomainRepository(BaseRepository[SourceDomain]):
    model = SourceDomain

    def upsert(self, domain: str, tier: str, credibility: float) -> None:
        self.session.merge(SourceDomain(domain=domain, tier=tier, credibility=credibility))
        self.session.flush()

    def credibility(self, domain: str) -> float | None:
        return self.session.scalar(select(SourceDomain.credibility).where(SourceDomain.domain == domain))
