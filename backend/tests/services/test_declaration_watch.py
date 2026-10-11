from datetime import date, datetime, timedelta, timezone

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import box

from app.domain.text import TextFingerprinter
from app.integrations.declaration_news import Fetched, FetchFailed, NewsHit
from app.models import AdminArea, DeclarationMention, DeclarationSource, DroughtDeclaration
from app.repositories.admin_area_repository import AdminAreaRepository
from app.repositories.declaration_repository import DeclarationRepository
from app.repositories.declaration_source_repository import DeclarationSourceRepository
from app.services.declaration_promoter import DeclarationPromoter
from app.services.declaration_watch import DeclarationWatchService

NOW = datetime(2026, 10, 11, 6, tzinfo=timezone.utc)
KA = [("Gadag", "Gadag"), ("Mundargi", "Gadag"), ("Ron", "Gadag"), ("Gokak", "Belgaum"), ("Indi", "Bijapur")]
AP = [("Adoni", "Kurnool"), ("Nandyal", "Kurnool"), ("Dhone", "Kurnool")]

SIASAT = ("Bengaluru: Karnataka added 40 more taluks to the drought list.\n"
          "The taluks added in the latest phase are Gadag, Mundargi, Ron and Gokak.")
DH = ("Karnataka government on Thursday declared more taluks drought-hit.\n"
      "The newly declared taluks include Gadag, Ron, Indi and Gokak, officials said.")
WIRE_COPY = SIASAT  # the same wire text on another site
ORDER = "Government of Karnataka. Revenue Department.\nThe following taluks are declared drought-affected: Indi, Gadag, Ron."
AP_LIST_KA_NAMED = "Karnataka officials said these were declared drought-hit: Adoni, Nandyal, Dhone."
DEMAND = "Karnataka farmers demand that these taluks be declared drought-hit: Gadag, Ron, Indi."


def html(text: str, links: str = "") -> bytes:
    return f"<html><body><article>{''.join(f'<p>{p}</p>' for p in text.splitlines())}{links}</article></body></html>".encode()


class FakeSearch:
    def __init__(self, hits):
        self.hits = hits

    def search(self):
        return list(self.hits)


class FakeFetcher:
    def __init__(self, pages: dict):
        self.pages = pages
        self.calls: list[str] = []

    def get(self, url, expect_pdf=False):
        self.calls.append(url)
        page = self.pages[url]
        if isinstance(page, Exception):
            raise page
        return Fetched(url, "application/pdf" if expect_pdf else "text/html", page)


def hit(url, day=date(2026, 10, 2)):
    from urllib.parse import urlsplit
    return NewsHit(url, urlsplit(url).hostname, "title", day)


@pytest.fixture
def areas(db):
    ids = {}
    for i, (name, district) in enumerate(KA):
        a = AdminArea(level="subdistrict", name=name, name_norm=name.lower(), state_code="KA", district_name=district,
                      geom=from_shape(box(74 + i * 0.1, 15, 74.05 + i * 0.1, 15.05), srid=4326))
        db.add(a)
        db.flush()
        ids[name] = a.id
    for i, (name, district) in enumerate(AP):
        a = AdminArea(level="subdistrict", name=name, name_norm=name.lower(), state_code="AP", district_name=district,
                      geom=from_shape(box(77 + i * 0.1, 15, 77.05 + i * 0.1, 15.05), srid=4326))
        db.add(a)
        db.flush()
        ids[name] = a.id
    return ids


def watch(db, hits, pages, pdf_text=lambda body: body.decode().splitlines()):
    fetcher = FakeFetcher(pages)
    service = DeclarationWatchService(FakeSearch(hits), fetcher, DeclarationSourceRepository(db), AdminAreaRepository(db),
                                      TextFingerprinter(), pdf_text=pdf_text)
    return service, fetcher


def promote(db):
    return DeclarationPromoter(DeclarationSourceRepository(db), DeclarationRepository(db), TextFingerprinter()).promote(NOW)


def declared(db) -> dict[str, DroughtDeclaration]:
    names = {a.id: a.name for a in db.query(AdminArea)}
    return {names[d.area_id]: d for d in db.query(DroughtDeclaration)}


def test_one_news_site_is_not_enough(db, areas):
    service, _ = watch(db, [hit("https://www.siasat.com/a")], {"https://www.siasat.com/a": html(SIASAT)})
    stats = service.run(NOW)
    assert stats["mentions"] == 4 and stats["by_status"] == {"listed": 1}
    assert promote(db)["waiting"] == 4 and declared(db) == {}


def test_two_independent_news_sites_declare_what_both_name(db, areas):
    pages = {"https://www.siasat.com/a": html(SIASAT), "https://www.deccanherald.com/b": html(DH)}
    service, _ = watch(db, [hit("https://www.siasat.com/a", date(2026, 10, 2)),
                            hit("https://www.deccanherald.com/b", date(2026, 10, 1))], pages)
    service.run(NOW)
    stats = promote(db)
    rows = declared(db)
    assert set(rows) == {"Gadag", "Ron", "Gokak"} and stats["declared"] == {"KA": 3}
    gadag = rows["Gadag"]
    assert gadag.declared_on == date(2026, 10, 1) and gadag.state_code == "KA"
    assert gadag.order_ref == "news: 2 sources (severity not stated)" and gadag.severity == "moderate"
    assert gadag.source_url == "https://www.deccanherald.com/b"


def test_a_wire_copy_on_another_site_is_not_a_second_source(db, areas):
    pages = {"https://www.siasat.com/a": html(SIASAT), "https://www.prokerala.com/c": html(WIRE_COPY)}
    service, _ = watch(db, [hit("https://www.siasat.com/a"), hit("https://www.prokerala.com/c")], pages)
    service.run(NOW)
    promote(db)
    assert declared(db) == {}


def test_an_official_order_linked_from_an_article_is_enough_alone(db, areas):
    link = '<a href="https://revenue.karnataka.gov.in/orders/drought-2026.pdf">order</a>'
    pages = {"https://www.siasat.com/a": html("Karnataka news about drought, no list here.", link),
             "https://revenue.karnataka.gov.in/orders/drought-2026.pdf": ORDER.encode()}
    service, fetcher = watch(db, [hit("https://www.siasat.com/a")], pages)
    service.run(NOW)
    promote(db)
    rows = declared(db)
    assert set(rows) == {"Indi", "Gadag", "Ron"}
    assert rows["Indi"].order_ref.startswith("official order")
    assert rows["Indi"].source_url == "https://revenue.karnataka.gov.in/orders/drought-2026.pdf"
    official = db.query(DeclarationSource).filter_by(kind="official").one()
    assert official.status == "listed" and official.state_code == "KA"


def test_seen_articles_are_never_read_again_and_failures_get_one_retry(db, areas):
    url = "https://www.siasat.com/a"
    service, fetcher = watch(db, [hit(url)], {url: FetchFailed("timeout")})
    service.run(NOW)
    service.run(NOW)            # second attempt
    service.run(NOW)            # no third attempt
    assert fetcher.calls == [url, url]
    source = db.query(DeclarationSource).one()
    assert (source.status, source.attempts) == ("failed", 2)
    ok_url = "https://www.deccanherald.com/b"
    service2, fetcher2 = watch(db, [hit(ok_url)], {ok_url: html(DH)})
    service2.run(NOW)
    service2.run(NOW)
    assert fetcher2.calls == [ok_url]


def test_names_from_another_state_with_the_wrong_state_named_are_skipped(db, areas):
    service, _ = watch(db, [hit("https://www.siasat.com/x")], {"https://www.siasat.com/x": html(AP_LIST_KA_NAMED)})
    assert service.run(NOW)["by_status"] == {"state_unclear": 1}
    assert db.query(DeclarationMention).count() == 0


def test_demands_are_not_declarations(db, areas):
    service, _ = watch(db, [hit("https://www.siasat.com/d")], {"https://www.siasat.com/d": html(DEMAND)})
    assert service.run(NOW)["by_status"] == {"no_list": 1}


def test_an_existing_declaration_is_never_rewritten_and_reruns_change_nothing(db, areas):
    DeclarationRepository(db).upsert(areas["Gadag"], "KA", date(2026, 9, 20), "severe", "KA order 20 Sep", None)
    pages = {"https://www.siasat.com/a": html(SIASAT), "https://www.deccanherald.com/b": html(DH)}
    service, _ = watch(db, [hit("https://www.siasat.com/a"), hit("https://www.deccanherald.com/b")], pages)
    service.run(NOW)
    promote(db)
    service.run(NOW)
    promote(db)
    rows = declared(db)
    assert rows["Gadag"].order_ref == "KA order 20 Sep" and rows["Gadag"].severity == "severe"
    assert db.query(DroughtDeclaration).count() == 3
    assert db.query(DeclarationMention).count() == 8


def test_a_mention_is_stored_once_per_source_and_taluka(db, areas):
    repo = DeclarationSourceRepository(db)
    source = repo.save(DeclarationSource(url="https://x.test/a", domain="x.test", kind="news", state_code="KA",
                                         title="t", published_on=date(2026, 10, 2), status="listed", attempts=1,
                                         checked_at=NOW))
    row = {"area_id": areas["Gadag"], "score": 100.0, "severity": None, "text": "Gadag"}
    repo.add_mentions(source.id, [row, dict(row, text="Gadag taluk")])
    repo.add_mentions(source.id, [row])
    assert db.query(DeclarationMention).count() == 1


def test_old_mentions_outside_the_season_do_not_count(db, areas):
    old = NOW.date() - timedelta(days=150)
    pages = {"https://www.siasat.com/a": html(SIASAT), "https://www.deccanherald.com/b": html(DH)}
    service, _ = watch(db, [hit("https://www.siasat.com/a", old), hit("https://www.deccanherald.com/b", old)], pages)
    service.run(NOW)
    promote(db)
    assert declared(db) == {}


def test_the_same_publisher_on_www_and_mobile_hosts_is_one_source(db, areas):
    pages = {"https://www.siasat.com/a": html(SIASAT), "https://m.siasat.com/b": html(DH)}
    service, _ = watch(db, [hit("https://www.siasat.com/a"), hit("https://m.siasat.com/b")], pages)
    service.run(NOW)
    promote(db)
    assert declared(db) == {}


class CountingWatch:
    def __init__(self):
        self.runs = 0

    def run(self, now):
        self.runs += 1
        return {"hits": 0}


class CountingPromoter:
    def promote(self, now):
        return {"declared": {}, "waiting": 0}


def test_the_stage_runs_at_most_once_every_20_hours(db):
    from app.models import PipelineRun
    from app.repositories.pipeline_run_repository import PipelineRunRepository
    from app.services.pipeline import DeclarationWatchStage, PipelineContext

    runs = PipelineRunRepository(db)
    db.add(PipelineRun(kind="local", started_at=NOW - timedelta(hours=5), finished_at=NOW - timedelta(hours=5),
                       stats={"watch": {"error": "ExternalServiceError: gdelt down"}}))  # a failed watch: not counted
    db.flush()
    watch_, stage_args = CountingWatch(), {}
    stage = DeclarationWatchStage(watch_, CountingPromoter(), runs)
    ctx = PipelineContext(now=NOW, run_id="r1")
    stage.run(ctx)
    assert watch_.runs == 1 and ctx.stats["watch"]["promoted"] == {"declared": {}, "waiting": 0}
    db.add(PipelineRun(kind="local", started_at=NOW - timedelta(hours=3), finished_at=NOW - timedelta(hours=3),
                       stats={"watch": {"hits": 12}}))
    db.flush()
    ctx = PipelineContext(now=NOW, run_id="r2")
    stage.run(ctx)
    assert watch_.runs == 1 and ctx.stats["watch"] == {"skipped": "ran 3h ago"}
    DeclarationWatchStage(watch_, CountingPromoter(), runs, force=True).run(PipelineContext(now=NOW, run_id="r3"))
    later = PipelineContext(now=NOW + timedelta(hours=21), run_id="r4")
    stage.run(later)
    assert watch_.runs == 3


def test_the_review_list_has_what_is_named_but_not_declared(db, areas):
    from app.cli.declaration_review import review_rows
    pages = {"https://www.siasat.com/a": html(SIASAT), "https://www.deccanherald.com/b": html(DH)}
    service, _ = watch(db, [hit("https://www.siasat.com/a", date(2026, 10, 2)),
                            hit("https://www.deccanherald.com/b", date(2026, 10, 1))], pages)
    service.run(NOW)
    promote(db)  # Gadag, Ron, Gokak declared; Mundargi (siasat only) and Indi (DH only) wait
    rows = review_rows(db, NOW)
    assert {(r["taluka"], r["source_url"]) for r in rows} == {("Mundargi", "https://www.siasat.com/a"),
                                                               ("Indi", "https://www.deccanherald.com/b")}
    mundargi = next(r for r in rows if r["taluka"] == "Mundargi")
    assert mundargi["state_code"] == "KA" and mundargi["district"] == "Gadag" and mundargi["area_id"] == areas["Mundargi"]
    assert mundargi["severity"] == "unknown" and mundargi["declared_on"] == "2026-10-02"
    assert mundargi["order_ref"] == "news: 1 source (check before loading)"
