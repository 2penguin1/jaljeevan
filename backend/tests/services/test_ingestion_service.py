from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.domain.entities import RawItem
from app.domain.prefilter import Prefilter
from app.domain.text import TextFingerprinter
from app.integrations.archive import LocalRawArchive
from app.models import Signal, SourceDomain
from app.repositories.signal_repository import SignalRepository
from app.repositories.source_domain_repository import SourceDomainRepository
from app.services.credibility_resolver import CredibilityResolver
from app.services.ingestion_service import IngestionService

NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)
BODY = ("Residents of Mahadevapura said municipal water supply has been cut for eleven days and "
        "private tanker prices doubled. Officials said borewells dried up after a weak monsoon. ") * 3


def make_service(db, tmp_path) -> IngestionService:
    return IngestionService(SignalRepository(db), CredibilityResolver(SourceDomainRepository(db)),
                            Prefilter.default(max_age_days=30), TextFingerprinter(), LocalRawArchive(tmp_path))


def raw(url, title="Bengaluru water crisis deepens", text=BODY, **kw) -> RawItem:
    return RawItem(source=kw.pop("source", "gdelt"), url=url, title=title, text=text,
                   published_at=kw.pop("published_at", NOW), country="IN",
                   domain=kw.pop("domain", "thehindu.com"), **kw)


def test_inserts_new_signals_and_archives_raw(db, tmp_path):
    result = make_service(db, tmp_path).ingest("gdelt", [raw("https://a.test/1")], NOW, "run1")
    assert result.inserted == 1 and len(result.pending_ids) == 1
    assert result.raw_key and result.raw_key.endswith("run1.jsonl")
    sig = db.get(Signal, result.pending_ids[0])
    assert sig.status == "pending" and sig.raw_s3_key == result.raw_key


def test_exact_duplicates_are_skipped(db, tmp_path):
    svc = make_service(db, tmp_path)
    svc.ingest("gdelt", [raw("https://a.test/1")], NOW, "r1")
    again = svc.ingest("gdelt", [raw("https://a.test/1")], NOW, "r2")
    assert again.inserted == 0 and again.duplicate == 1


def test_near_duplicate_wire_copy_is_marked_and_not_classified(db, tmp_path):
    svc = make_service(db, tmp_path)
    first = svc.ingest("gdelt", [raw("https://a.test/1")], NOW, "r1")
    copy = svc.ingest("gdelt", [raw("https://b.test/9", title="Water crisis deepens in Bengaluru as taps run dry",
                                    domain="ndtv.com")], NOW, "r2")
    assert copy.near_duplicate == 1 and copy.pending_ids == []
    row = db.scalar(select(Signal).where(Signal.url == "https://b.test/9"))
    assert row.dup_of == first.pending_ids[0] and row.rejected_reason == "near_duplicate"


def test_prefilter_rejects_are_stored_with_reason(db, tmp_path):
    result = make_service(db, tmp_path).ingest(
        "gdelt", [raw("https://a.test/old", published_at=NOW - timedelta(days=60))], NOW, "r1")
    assert result.rejected == {"too_old": 1} and result.pending_ids == []
    row = db.scalar(select(Signal).where(Signal.url == "https://a.test/old"))
    assert row.status == "rejected" and row.rejected_reason == "too_old"


def test_empty_batch_writes_no_archive(db, tmp_path):
    result = make_service(db, tmp_path).ingest("gdelt", [], NOW, "r1")
    assert result.inserted == 0 and result.raw_key is None


def test_credibility_tiers(db):
    db.add(SourceDomain(domain="thehindu.com", tier="national", credibility=0.8))
    db.flush()
    resolver = CredibilityResolver(SourceDomainRepository(db))
    assert resolver.score("gdelt", "thehindu.com") == 0.8
    assert resolver.score("gdelt", "www.thehindu.com") == 0.8
    assert resolver.score("rss", "rajasthan.gov.in") == 1.0
    assert resolver.score("reddit", "reddit.com") == 0.4
    assert resolver.score("citizen", None) == 0.5
    assert resolver.score("gdelt", "unknownblog.in") == 0.6
