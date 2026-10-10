from app.repositories.source_domain_repository import SourceDomainRepository


class CredibilityResolver:
    """How much to trust a post's source (spec tiers). Used to weight evidence when scoring zones."""

    FIXED = {"reddit": 0.4, "x": 0.4, "citizen": 0.5}
    OFFICIAL = 1.0
    DEFAULT_NEWS = 0.6
    _OFFICIAL_SUFFIXES = (".gov.in", ".nic.in")

    def __init__(self, domains: SourceDomainRepository):
        self.domains = domains

    def score(self, source: str, domain: str | None) -> float:
        if source in self.FIXED:
            return self.FIXED[source]
        host = (domain or "").lower().removeprefix("www.")
        if host.endswith(self._OFFICIAL_SUFFIXES):
            return self.OFFICIAL
        known = self.domains.credibility(host) if host else None
        return known if known is not None else self.DEFAULT_NEWS
