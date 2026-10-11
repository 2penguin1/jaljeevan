import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, box

from app.core.exceptions import ConflictError, ForbiddenError
from app.integrations.ports import LLMResult
from app.models import Organization, Tender, User, Zone
from app.repositories.brief_repository import BriefRepository
from app.repositories.tender_repository import TenderRepository
from app.services.brief_service import BriefDraft, BriefService
from app.services.tender_service import TenderService

EVIDENCE = [{"signal_id": "s1", "quote": "wells have run dry", "summary": "Wells dry in Akkalkot", "place": "Akkalkot"},
            {"signal_id": "s2", "quote": "tankers come once a week", "summary": "Tankers irregular", "place": "Akkalkot"}]


class FakeLLM:
    def __init__(self, draft: BriefDraft | None):
        self.draft = draft
        self.prompts: list[str] = []

    def parse(self, *, system, user, schema, max_tokens):
        self.prompts.append(user)
        return LLMResult(parsed=self.draft, provider="fake:test")


@pytest.fixture
def world(db):
    gov = Organization(kind="government", name="Relief, Maharashtra", state_code="MH")
    db.add(gov)
    db.flush()
    officer = User(email="o@b.test", password_hash="!", name="Officer", role="gov_admin", org_id=gov.id)
    vendor_org = Organization(kind="vendor", name="Near Tankers", state_code="MH", tanker_count=12, tanker_capacity_kl=10,
                              base_price_per_kl=60, reliability=0.9, geom=from_shape(Point(76.2, 17.6), srid=4326))
    db.add_all([officer, vendor_org])
    db.flush()
    vendor = User(email="v@b.test", password_hash="!", name="Vendor", role="vendor", org_id=vendor_org.id)
    zone = Zone(name="Akkalkot taluka, Solapur", hazard="drought", zone_type="taluka", status="active", score=79,
                population_est=381611, population_urban=81621, geom=from_shape(box(76.0, 17.3, 76.4, 17.7), srid=4326),
                centroid=from_shape(Point(76.21, 17.53), srid=4326))
    db.add_all([vendor, zone])
    db.flush()
    return db, zone, officer, vendor


def service(db, llm):
    return BriefService(BriefRepository(db), TenderRepository(db), TenderService(TenderRepository(db)), llm,
                        evidence=lambda zone_id, limit=None: EVIDENCE[:limit])


def test_the_ai_writes_words_and_code_writes_every_number(world):
    db, zone, officer, _ = world
    llm = FakeLLM(BriefDraft(situation="Wells have run dry. About 50,000 people are affected. Tankers are irregular.",
                             action_keys=["tanker_rounds", "launch_rockets", "fodder_camps"], cited_signal_ids=["s1", "s99"]))
    brief = service(db, llm).draft(zone.id, officer)
    assert brief["status"] == "draft" and brief["version"] == 1
    assert brief["summary"] == "Wells have run dry. Tankers are irregular."          # the sentence with a number is gone
    assert [a["key"] for a in brief["actions"]] == ["tanker_rounds", "fodder_camps"]  # invented action dropped
    assert brief["cited_signal_ids"] == ["s1"]                                       # only this zone's evidence
    assert (brief["need_per_day"], brief["units_per_day"], brief["duration_days"]) == (600.0, 60, 30)
    assert brief["suggested_price_per_unit"] == 60.0 and brief["budget_inr"] == 600 * 30 * 60
    assert brief["written_by"] == "fake:test"
    assert "wells have run dry" in llm.prompts[0] and "600" in llm.prompts[0]  # the AI is given the facts, not asked


def test_when_the_ai_is_unavailable_a_plain_summary_is_used_and_the_numbers_still_stand(world):
    db, zone, officer, _ = world
    brief = service(db, FakeLLM(None)).draft(zone.id, officer)
    assert brief["summary"] and brief["need_per_day"] == 600.0 and brief["written_by"] == "template"
    assert [a["key"] for a in brief["actions"]][:1] == ["tanker_rounds"]


def test_only_an_officer_drafts_and_approving_publishes_the_prefilled_tender(world):
    db, zone, officer, vendor = world
    svc = service(db, FakeLLM(BriefDraft(situation="Wells are dry.", action_keys=["tanker_rounds"], cited_signal_ids=["s1"])))
    with pytest.raises(ForbiddenError):
        svc.draft(zone.id, vendor)
    brief = svc.draft(zone.id, officer)
    with pytest.raises(ForbiddenError):
        svc.approve(brief["id"], vendor)
    tender_id = svc.approve(brief["id"], officer)
    tender = db.get(Tender, tender_id)
    assert (tender.qty_per_day, tender.duration_days, tender.price_per_unit, tender.brief_id) == (600.0, 30, 60.0, brief["id"])
    assert svc.get(brief["id"], viewer=None)["status"] == "approved"
    with pytest.raises(ConflictError):
        svc.approve(brief["id"], officer)  # already approved


def test_drafts_are_private_to_officers_and_a_rejected_brief_keeps_the_reason(world):
    db, zone, officer, vendor = world
    svc = service(db, FakeLLM(BriefDraft(situation="Wells are dry.", action_keys=[], cited_signal_ids=[])))
    first = svc.draft(zone.id, officer)
    assert svc.latest_for_zone(zone.id, viewer=None) is None and svc.latest_for_zone(zone.id, viewer=vendor) is None
    assert svc.latest_for_zone(zone.id, viewer=officer)["id"] == first["id"]
    assert [b["id"] for b in svc.queue(officer)] == [first["id"]]
    svc.reject(first["id"], officer, "Need village names")
    assert svc.get(first["id"], viewer=officer)["review_notes"] == "Need village names"
    assert svc.draft(zone.id, officer)["version"] == 2


def test_a_zone_without_a_population_estimate_gets_no_brief_instead_of_a_zero_one(world):
    from app.core.exceptions import DomainValidationError
    db, zone, officer, _ = world
    zone.population_est, zone.population_urban = None, None
    db.flush()
    with pytest.raises(DomainValidationError, match="population"):
        service(db, FakeLLM(None)).draft(zone.id, officer)


class SlowLLM:
    def parse(self, *, system, user, schema, max_tokens):
        import time
        time.sleep(3)
        return LLMResult(parsed=BriefDraft(situation="Too late.", action_keys=[], cited_signal_ids=[]), provider="slow")


def test_a_slow_ai_falls_back_to_the_template_in_time(world, monkeypatch):
    import time
    from app.services import brief_service
    monkeypatch.setattr(brief_service, "AI_DEADLINE_S", 0.5)
    db, zone, officer, _ = world
    started = time.monotonic()
    brief = service(db, SlowLLM()).draft(zone.id, officer)
    assert time.monotonic() - started < 2.5 and brief["written_by"] == "template"


def test_drafting_again_returns_the_open_draft_and_after_approval_a_new_version_is_made(world):
    db, zone, officer, _ = world
    svc = service(db, FakeLLM(BriefDraft(situation="Wells are dry.", action_keys=[], cited_signal_ids=[])))
    first = svc.draft(zone.id, officer)
    assert svc.draft(zone.id, officer)["id"] == first["id"]  # a double click never makes two drafts
    svc.approve(first["id"], officer)
    assert svc.draft(zone.id, officer)["version"] == 2
