"""The intelligence pipeline: Ingest -> Classify -> Geocode -> Zones, each stage with the same `run(ctx)` shape.

The same stage classes run in one process (CLI / API job) or one-per-Lambda on AWS (P2).
"""
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.core.exceptions import ExternalServiceError
from app.domain.events import SignalClassified
from app.integrations.article import ArticleExtractor
from app.integrations.sources.registry import FetcherRegistry
from app.models import PipelineRun
from app.repositories.pipeline_run_repository import PipelineRunRepository
from app.repositories.signal_repository import SignalRepository
from app.services.classification_service import ClassificationService
from app.services.declaration_promoter import DeclarationPromoter
from app.services.declaration_watch import DeclarationWatchService
from app.services.geocoding.geocoding_service import GeocodingService
from app.services.indicator_refresh_service import IndicatorRefreshService
from app.services.ingestion_service import IngestionService
from app.services.weather_service import WeatherService
from app.services.zone_detection_service import ZoneDetectionService

LOG = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    now: datetime
    run_id: str
    stats: dict = field(default_factory=dict)
    pending_ids: list[uuid.UUID] = field(default_factory=list)
    classified_ids: list[uuid.UUID] = field(default_factory=list)
    events: list = field(default_factory=list)


@dataclass
class PipelineOutcome:
    run: PipelineRun
    events: list  # dispatch these through the EventBus AFTER the transaction commits


class PipelineStage(Protocol):
    name: str

    def run(self, ctx: PipelineContext) -> None: ...


class IngestStage:
    name = "ingest"

    def __init__(self, registry: FetcherRegistry, ingestion: IngestionService, articles: ArticleExtractor,
                 weather: WeatherService):
        self.registry = registry
        self.ingestion = ingestion
        self.articles = articles
        self.weather = weather

    def run(self, ctx: PipelineContext) -> None:
        stats: dict = {}
        for fetcher in self.registry.enabled():
            try:
                items = fetcher.fetch()
                if fetcher.name == "gdelt":
                    items = self.articles.enrich(items)  # GDELT gives headlines only
            except ExternalServiceError as exc:
                LOG.warning("source %s failed: %s", fetcher.name, exc)
                stats[fetcher.name] = {"error": str(exc)}
                continue
            result = self.ingestion.ingest(fetcher.name, items, ctx.now, ctx.run_id)
            ctx.pending_ids += result.pending_ids
            stats[fetcher.name] = {"fetched": len(items), "inserted": result.inserted,
                                   "duplicate": result.duplicate, "near_duplicate": result.near_duplicate,
                                   "rejected": result.rejected}
        stats["weather"] = {"districts": self.weather.refresh(ctx.now.date())}
        ctx.stats[self.name] = stats


class IndicatorStage:
    """Measured drought data per taluka (rainfall SPI, soil moisture). Downloads only when a newer period exists."""

    name = "indicators"

    def __init__(self, refresher: IndicatorRefreshService):
        self.refresher = refresher

    def run(self, ctx: PipelineContext) -> None:
        ctx.stats[self.name] = self.refresher.refresh(ctx.now)


class DeclarationWatchStage:
    """Official drought declarations from the news (other states): read new articles, then apply the safety rule.
    Runs at most once every 20 hours: GDELT and news sites are asked politely, declarations change slowly."""

    name = "watch"

    def __init__(self, watch: DeclarationWatchService, promoter: DeclarationPromoter, runs: PipelineRunRepository,
                 min_gap: timedelta = timedelta(hours=20), force: bool = False):
        self.watch = watch
        self.promoter = promoter
        self.runs = runs
        self.min_gap = min_gap
        self.force = force

    def run(self, ctx: PipelineContext) -> None:
        last = self.runs.last_success(self.name)
        if not self.force and last is not None and ctx.now - last < self.min_gap:
            ctx.stats[self.name] = {"skipped": f"ran {int((ctx.now - last).total_seconds() // 3600)}h ago"}
            return
        stats = self.watch.run(ctx.now)
        stats["promoted"] = self.promoter.promote(ctx.now)
        ctx.stats[self.name] = stats


class ClassifyStage:
    name = "classify"

    def __init__(self, classifier: ClassificationService, signals: SignalRepository, max_backlog: int = 500):
        self.classifier = classifier
        self.signals = signals
        self.max_backlog = max_backlog

    def run(self, ctx: PipelineContext) -> None:
        ids = list(dict.fromkeys([*ctx.pending_ids, *self.signals.pending_ids(self.max_backlog)]))
        stats = self.classifier.classify(ids, contrasts=self.signals.recent_contrasts())
        relevant = self.signals.relevant_classified(ids)
        ctx.classified_ids = [s.id for s in relevant]
        ctx.events += [SignalClassified(s.id) for s in relevant]
        ctx.stats[self.name] = stats.as_dict()


class GeocodeStage:
    name = "geocode"

    def __init__(self, geocoder: GeocodingService, signals: SignalRepository):
        self.geocoder = geocoder
        self.signals = signals

    def run(self, ctx: PipelineContext) -> None:
        located = 0
        for signal in self.signals.get_many(ctx.classified_ids):
            located += self.geocoder.geocode(signal) > 0
        ctx.stats[self.name] = {"signals": len(ctx.classified_ids), "located": located}


class ZoneStage:
    name = "zones"

    def __init__(self, detector: ZoneDetectionService):
        self.detector = detector

    def run(self, ctx: PipelineContext) -> None:
        result = self.detector.detect(ctx.now)
        ctx.events += result.events
        ctx.stats[self.name] = result.as_dict()


class IntelligencePipeline:
    """Runs the stages in order inside the caller's transaction and records the run in pipeline_runs."""

    def __init__(self, stages: list[PipelineStage], runs: PipelineRunRepository):
        self.stages = stages
        self.runs = runs

    def run(self, now: datetime, run_id: uuid.UUID | None = None, skip: set[str] = frozenset(),
            kind: str = "local") -> PipelineOutcome:
        run = (self.runs.find(run_id) if run_id else None) or self.runs.start(kind, now)
        if not self.runs.try_lock():
            self.runs.finish(run, {"skipped": "another run in progress"}, datetime.now(timezone.utc))
            return PipelineOutcome(run=run, events=[])
        ctx = PipelineContext(now=now, run_id=str(run.id))
        for stage in self.stages:
            if stage.name in skip:
                continue
            self._run_stage(stage, ctx)
        self.runs.finish(run, ctx.stats, datetime.now(timezone.utc))
        return PipelineOutcome(run=run, events=ctx.events)

    def _run_stage(self, stage: PipelineStage, ctx: PipelineContext) -> None:
        """Each stage runs inside a savepoint: a failure undoes only that stage, keeps earlier (paid) work,
        and is recorded in the run's stats instead of discarding the whole run."""
        events_before = len(ctx.events)
        savepoint = self.runs.savepoint()
        try:
            stage.run(ctx)
            savepoint.commit()
        except Exception as exc:  # noqa: BLE001 - isolate stages; the error is recorded, not swallowed
            savepoint.rollback()
            del ctx.events[events_before:]
            LOG.exception("pipeline stage %s failed", stage.name)
            ctx.stats[stage.name] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
