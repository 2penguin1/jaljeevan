"""Regression tests for the final-review findings (each failed before its fix)."""
import logging
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, Polygon
from sqlalchemy import select

from app.core.exceptions import ExternalServiceError
from app.domain.classification import BatchResult, Label, PostInput, PostResult, PromptBuilder
from app.domain.entities import RawItem
from app.domain.evidence import EvidenceValidator
from app.domain.geo import LocationQuery
from app.domain.prefilter import Prefilter
from app.domain.taxonomy import Taxonomy
from app.domain.text import TextFingerprinter
from app.integrations.apify import ApifyClient
from app.integrations.archive import LocalRawArchive
from app.integrations.ports import LLMResult
from app.integrations.sources.gdelt import GdeltFetcher
from app.models import AdminArea, Signal, SignalLabel
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.geocode_cache_repository import GeocodeCacheRepository
from app.repositories.indicator_repository import IndicatorRepository
from app.repositories.pipeline_run_repository import PipelineRunRepository
from app.repositories.signal_repository import SignalRepository
from app.repositories.source_domain_repository import SourceDomainRepository
from app.services.classification_service import ClassificationService
from app.services.credibility_resolver import CredibilityResolver
from app.services.geo_seed_service import GeoSeedService
from app.services.geocoding.resolvers import GazetteerResolver, LocatorResolver, ResolverChain
from app.services.ingestion_service import IngestionService
from app.services.pipeline import IntelligencePipeline

NOW = datetime.now(timezone.utc)
tax = Taxonomy.load()


def classifier(db, llm) -> ClassificationService:
    return ClassificationService(SignalRepository(db), llm, PromptBuilder(tax), EvidenceValidator(tax), tax)


def ingestion(db, tmp_path) -> IngestionService:
    return IngestionService(SignalRepository(db), CredibilityResolver(SourceDomainRepository(db)),
                            Prefilter.default(30), TextFingerprinter(), LocalRawArchive(tmp_path))


# 1. a duplicate label code must not abort the run
def test_duplicate_label_code_is_collapsed(db):
    s = Signal(source="rss", url="https://f/1", title="", content_hash="f1", simhash=0,
               text="No water for 11 days here. Taps are dry every morning in our lane.")
    db.add(s)
    db.flush()
    dup = PostResult(id="0", relevant=True, event_period="current", event_date=None, first_hand=True,
                     labels=[Label(code="SUPPLY.DRY_TAPS", severity=3, evidence="No water for 11 days"),
                             Label(code="SUPPLY.DRY_TAPS", severity=4, evidence="Taps are dry every morning")],
                     locations=[], people_affected_hint=None, english_summary="x")

    class LLM:
        def parse(self, **kw):
            return LLMResult(parsed=BatchResult(results=[dup]), usage={})

    classifier(db, LLM()).classify([s.id])
    labels = db.scalars(select(SignalLabel).where(SignalLabel.signal_id == s.id)).all()
    assert len(labels) == 1 and labels[0].severity == 4  # keeps the more severe one


def test_long_error_name_fits_rejected_reason(db):
    s = Signal(source="rss", url="https://f/2", title="", text="water crisis in the colony again",
               content_hash="f2", simhash=0)
    db.add(s)
    db.flush()

    class AVeryLongBotocoreStyleExceptionNameError(Exception):
        pass

    class LLM:
        def parse(self, **kw):
            raise AVeryLongBotocoreStyleExceptionNameError()

    classifier(db, LLM()).classify([s.id])
    db.refresh(s)
    assert s.status == "failed" and len(s.rejected_reason) <= 40


# 2. the Apify token must never reach logs or URLs
def test_apify_token_sent_as_header_not_logged(caplog):
    seen = {}

    def handler(req):
        seen["auth"], seen["url"] = req.headers.get("authorization"), str(req.url)
        return httpx.Response(201, json=[])

    caplog.set_level(logging.DEBUG)
    ApifyClient(httpx.Client(transport=httpx.MockTransport(handler)), "SECRET-T0KEN", 0.5).run_actor("a/b", {}, 10)
    assert seen["auth"] == "Bearer SECRET-T0KEN" and "SECRET-T0KEN" not in seen["url"]
    assert "SECRET-T0KEN" not in caplog.text


# 4. state / country names never become fine points through the locator
def test_state_or_country_mention_is_never_geocoded(db):
    db.add(AdminArea(level="district", name="Bangalore Urban", name_norm="bangalore urban", state_code="KA",
                     geom=from_shape(Polygon([(77.4, 12.8), (77.8, 12.8), (77.8, 13.2), (77.4, 13.2)]), srid=4326)))
    db.flush()

    class Locator:
        def geocode(self, q):
            return [(77.6, 13.0)]  # would pass the state check

    areas = AdminAreaRepository(db)
    chain = ResolverChain([GazetteerResolver(areas), LocatorResolver(Locator(), GeocodeCacheRepository(db), areas)])
    assert chain.resolve(LocationQuery("Karnataka", "Karnataka", None, "town")) is None
    assert chain.resolve(LocationQuery("India", None, None, "town")) is None
    assert chain.resolve(LocationQuery("Bharat", None, None, "village")) is None


# 5. same story, headline only, different outlets -> near duplicate
def test_headline_only_rewrites_are_near_duplicates(db, tmp_path):
    svc = ingestion(db, tmp_path)
    a = RawItem(source="rss", url="https://n/1", text="", published_at=NOW, domain="thehindu.com", country="IN",
                title="Bengaluru water crisis: Mahadevapura taps dry for 11 days - The Hindu")
    b = RawItem(source="rss", url="https://n/2", text="", published_at=NOW, domain="ndtv.com", country="IN",
                title="Mahadevapura taps dry for 11 days amid Bengaluru water crisis - NDTV")
    first = svc.ingest("rss", [a], NOW, "r1")
    second = svc.ingest("rss", [b], NOW, "r2")
    assert first.inserted == 1 and second.near_duplicate == 1 and second.pending_ids == []


def test_unrelated_short_headlines_are_not_merged(db, tmp_path):
    svc = ingestion(db, tmp_path)
    svc.ingest("rss", [RawItem(source="rss", url="https://n/3", text="", published_at=NOW, country="IN",
                               title="Chennai water tanker strike enters day 3 - DT Next")], NOW, "r1")
    other = svc.ingest("rss", [RawItem(source="rss", url="https://n/4", text="", published_at=NOW, country="IN",
                                       title="Flood alert issued for Assam districts - India Today")], NOW, "r2")
    assert other.near_duplicate == 0 and len(other.pending_ids) == 1


# 6. a failing stage keeps earlier stages' work and records the error
def test_failing_stage_keeps_earlier_work_and_records_error(db):
    class Writes:
        name = "ingest"

        def run(self, ctx):
            db.add(Signal(source="rss", url="https://s/1", title="t", text="x", content_hash="s1", simhash=0))
            db.flush()

    class Boom:
        name = "zones"

        def run(self, ctx):
            db.add(Signal(source="rss", url="https://s/2", title="t", text="x", content_hash="s2", simhash=0))
            db.flush()
            raise RuntimeError("postgis exploded")

    outcome = IntelligencePipeline([Writes(), Boom()], PipelineRunRepository(db)).run(NOW)
    assert outcome.run.finished_at is not None
    assert outcome.run.stats["zones"] == {"error": "RuntimeError: postgis exploded"}
    urls = set(db.scalars(select(Signal.url)))
    assert "https://s/1" in urls and "https://s/2" not in urls  # failed stage rolled back to its savepoint


# 7. admin endpoints locked when no token is configured
def test_admin_locked_when_token_unset(monkeypatch):
    from app.main import app
    monkeypatch.setattr("app.api.dependencies.settings.admin_token", None)
    with TestClient(app) as c:
        assert c.get("/admin/pipeline/runs", headers={"X-Admin-Token": ""}).status_code == 401
        assert c.get("/admin/pipeline/runs", headers={"X-Admin-Token": "anything"}).status_code == 401


def test_settings_ship_without_admin_token(monkeypatch):
    from app.core.config import Settings
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    assert Settings(_env_file=None).admin_token is None


# 8. alternate names resolve (Gurugram / Gurgaon)
def test_alias_names_resolve_in_gazetteer(db):
    db.add(AdminArea(level="town", name="Gurgaon", name_norm="gurgaon", aliases_norm=["gurugram", "गुड़गांव"],
                     state_code="HR", population=876824, geom=from_shape(Point(77.03, 28.46), srid=4326)))
    db.flush()
    r = GazetteerResolver(AdminAreaRepository(db)).resolve(LocationQuery("Gurugram", "Haryana", None, "town"))
    assert r is not None and r.confidence >= 0.9


def test_geonames_alternate_names_are_loaded(db, tmp_path):
    admin1 = tmp_path / "a.txt"
    admin1.write_text("IN.10\tHaryana\tHaryana\t1\n", encoding="utf-8")
    places = tmp_path / "IN.txt"
    row = ["1", "Gurgaon", "Gurgaon", "Gurugram,गुड़गांव,Gurgaon", "28.46", "77.03", "P", "PPLA2", "IN", "", "10",
           "", "", "", "876824", "", "", "Asia/Kolkata", "2024-01-01"]
    places.write_text("\t".join(row) + "\n", encoding="utf-8")
    GeoSeedService(AdminAreaRepository(db), IndicatorRepository(db), SourceDomainRepository(db)).load_geonames(places, admin1)
    town = db.scalar(select(AdminArea).where(AdminArea.name == "Gurgaon"))
    assert "gurugram" in town.aliases_norm and "gurgaon" not in town.aliases_norm  # no self-duplicate


# 9a. an odd GDELT payload stays inside per-source isolation
def test_gdelt_json_list_payload_is_an_external_error():
    fetcher = GdeltFetcher(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[1, 2]))),
                           sleep=lambda s: None)
    with pytest.raises(ExternalServiceError):
        fetcher.fetch()


# 9b. reviewer contrasts go in the untrusted user turn, not the cached system prompt
def test_contrasts_live_in_user_turn():
    builder = PromptBuilder(tax)
    user, _ = builder.user([PostInput("k", "rss", None, "t", "no water")], contrasts=["A water polo result."])
    assert "water polo" in user and user.index("water polo") < user.index("<post id=")
    assert "water polo" not in builder.system()
