"""Composition root: builds every object once and wires dependencies.

App-scoped singletons (shared, stateless) live as attributes. Anything that needs a database Session is
created per job by a factory method that takes the Session, so sessions are never shared across jobs.
"""
import uuid
from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path

import httpx
from cachetools import TTLCache
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import session_scope
from app.domain.classification import PromptBuilder
from app.domain.events import SignalClassified, ZoneEscalated
from app.domain.evidence import EvidenceValidator
from app.domain.hazards import HazardPolicies
from app.domain.lifecycle import ZoneStateMachine
from app.domain.prefilter import Prefilter
from app.domain.scoring import ScoringConfig, ZoneScorer
from app.domain.taxonomy import Taxonomy
from app.domain.text import TextFingerprinter
from app.domain.zones import ZoneTypeClassifier
from app.integrations.apify import ApifyClient
from app.integrations.archive import make_archive
from app.integrations.article import ArticleExtractor
from app.integrations.ports import LLMClient, RawArchive
from app.integrations.sources.gdelt import GdeltFetcher
from app.integrations.sources.registry import FetcherRegistry
from app.integrations.sources.rss import RssFetcher
from app.integrations.sources.social import RedditFetcher, XFetcher
from app.integrations.weather import OpenMeteoProvider
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.geocode_cache_repository import GeocodeCacheRepository
from app.repositories.indicator_repository import IndicatorRepository
from app.repositories.map_repository import MapRepository
from app.repositories.pipeline_run_repository import PipelineRunRepository
from app.repositories.read_repository import ReadRepository
from app.repositories.signal_repository import SignalRepository
from app.repositories.source_domain_repository import SourceDomainRepository
from app.repositories.zone_repository import ZoneRepository
from app.services.classification_service import ClassificationService
from app.services.credibility_resolver import CredibilityResolver
from app.services.event_bus import EventBus
from app.services.geocoding.geocoding_service import GeocodingService
from app.services.geocoding.resolvers import GazetteerResolver, LocatorResolver, ResolverChain
from app.services.ingestion_service import IngestionService
from app.services.map_query_service import MapQueryService
from app.services.read_query_service import ReadQueryService
from app.services.pipeline import (ClassifyStage, GeocodeStage, IngestStage, IntelligencePipeline,
                                   PipelineOutcome, ZoneStage)
from app.services.subscribers import AlertLogSubscriber, LiveFeedNotifier
from app.services.weather_service import WeatherService
from app.services.zone_detection_service import ZoneDetectionService

_DEFAULT = object()  # "build the real one" (lets tests pass None to mean "none at all")


class Container:
    def __init__(self, settings: Settings, *, llm: LLMClient | None = None, locator=_DEFAULT,
                 registry: FetcherRegistry | None = None, archive: RawArchive | None = None,
                 http: httpx.Client | None = None):
        self.settings = settings
        self.http = http or httpx.Client(headers={"User-Agent": "jal-hackathon/0.1"}, timeout=30)
        self._llm = llm
        self._locator = locator
        self._registry = registry
        self._archive = archive
        # stateless domain objects
        self.fingerprinter = TextFingerprinter()
        self.taxonomy = Taxonomy.load()
        self.prefilter = Prefilter.default(settings.max_post_age_days)
        self.prompts = PromptBuilder(self.taxonomy, self.fingerprinter)
        self.validator = EvidenceValidator(self.taxonomy, self.fingerprinter)
        self.scoring = ScoringConfig()
        self.scorer = ZoneScorer(self.scoring)
        self.machine = ZoneStateMachine(self.scoring)
        self.policies = HazardPolicies.default()
        self.zone_types = ZoneTypeClassifier()
        self.events = self._build_event_bus()
        self.district_cache: TTLCache = TTLCache(maxsize=8, ttl=600)  # map districts, per hazard

    # -- app-scoped adapters (lazy, so tests and offline runs never touch AWS) -------------------
    @cached_property
    def llm(self) -> LLMClient:
        """Providers in the configured order, wrapped in a fallback chain (Bedrock first: 'Built on AWS')."""
        if self._llm is not None:
            return self._llm
        from app.integrations.bedrock import BedrockLLMClient
        from app.integrations.fallback import FallbackLLMClient
        from app.integrations.groq import GroqLLMClient
        from app.integrations.nova import BedrockNovaClient

        s = self.settings
        builders = {
            "bedrock": lambda: BedrockLLMClient(s.aws_region, s.classify_model, s.aws_profile),
            "groq": lambda: GroqLLMClient(s.groq_api_key, s.groq_model) if s.groq_api_key else None,
            "nova": lambda: BedrockNovaClient(s.aws_region, s.nova_model, s.aws_profile),
        }
        clients = [c for name in s.llm_providers.split(",") if (c := builders[name.strip()]()) is not None]
        return clients[0] if len(clients) == 1 else FallbackLLMClient(clients)

    @cached_property
    def locator(self):
        if self._locator is not _DEFAULT:
            return self._locator
        from app.integrations.location import AmazonLocationClient
        return AmazonLocationClient(self.settings.aws_region, self.settings.aws_profile)

    @cached_property
    def archive(self) -> RawArchive:
        return self._archive or make_archive(self.settings.raw_bucket, Path(self.settings.raw_dir),
                                             self.settings.aws_region, self.settings.aws_profile)

    @cached_property
    def registry(self) -> FetcherRegistry:
        if self._registry is not None:
            return self._registry
        s = self.settings
        apify = ApifyClient(self.http, s.apify_token, s.apify_max_usd_per_run)
        registry = FetcherRegistry()
        for fetcher in (GdeltFetcher(self.http), RssFetcher(self.http),
                        RedditFetcher(apify, s.apify_reddit_actor, enabled=s.reddit_enabled),
                        XFetcher(apify, s.apify_x_actor)):
            registry.register(fetcher)
        return registry

    def _build_event_bus(self) -> EventBus:
        bus = EventBus()
        bus.subscribe(ZoneEscalated, AlertLogSubscriber())
        notifier = LiveFeedNotifier(session_scope)
        bus.subscribe(SignalClassified, notifier)
        bus.subscribe(ZoneEscalated, notifier)
        return bus

    # -- job-scoped factories (one Session per job) ---------------------------------------------
    def classification_service(self, session: Session) -> ClassificationService:
        return ClassificationService(SignalRepository(session), self.llm, self.prompts, self.validator,
                                     self.taxonomy)

    def geocoding_service(self, session: Session) -> GeocodingService:
        areas = AdminAreaRepository(session)
        resolvers = [GazetteerResolver(areas, self.fingerprinter)]
        if self.locator is not None:
            resolvers.append(LocatorResolver(self.locator, GeocodeCacheRepository(session), areas))
        return GeocodingService(ResolverChain(resolvers), SignalRepository(session))

    def zone_detection_service(self, session: Session) -> ZoneDetectionService:
        return ZoneDetectionService(ZoneRepository(session), AdminAreaRepository(session),
                                    IndicatorRepository(session), self.scorer, self.policies, self.machine,
                                    self.zone_types)

    def map_query_service(self, session: Session) -> MapQueryService:
        return MapQueryService(MapRepository(session), IndicatorRepository(session), self.policies,
                               self.district_cache)

    def read_query_service(self, session: Session) -> ReadQueryService:
        return ReadQueryService(ReadRepository(session), ZoneRepository(session), IndicatorRepository(session),
                                PipelineRunRepository(session), self.scorer, self.policies)

    def pipeline(self, session: Session) -> IntelligencePipeline:
        signals = SignalRepository(session)
        ingestion = IngestionService(signals, CredibilityResolver(SourceDomainRepository(session)), self.prefilter,
                                     self.fingerprinter, self.archive)
        weather = WeatherService(IndicatorRepository(session), OpenMeteoProvider(self.http))
        stages = [IngestStage(self.registry, ingestion, ArticleExtractor(self.http), weather),
                  ClassifyStage(self.classification_service(session), signals),
                  GeocodeStage(self.geocoding_service(session), signals),
                  ZoneStage(self.zone_detection_service(session))]
        return IntelligencePipeline(stages, PipelineRunRepository(session))

    # -- entry-point helper: one transaction, then events -----------------------------------------
    def run_pipeline_job(self, run_id: uuid.UUID | None = None, skip: set[str] = frozenset()) -> PipelineOutcome:
        with session_scope() as session:
            outcome = self.pipeline(session).run(datetime.now(timezone.utc), run_id=run_id, skip=skip)
        self.events.dispatch(outcome.events)  # after commit, by design
        return outcome
