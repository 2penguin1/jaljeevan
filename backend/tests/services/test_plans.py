from datetime import datetime, timezone

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import Point, box

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.integrations.ports import LLMResult
from app.models import User, Zone
from app.repositories.plan_repository import PlanRepository
from app.services.plan_service import PlanDraft, PlanService

TREND = [{"at": datetime(2026, 9, 1, tzinfo=timezone.utc), "score": 40.0},
         {"at": datetime(2026, 10, 10, tzinfo=timezone.utc), "score": 79.0}]


class FakeLLM:
    def __init__(self, draft):
        self.draft = draft

    def parse(self, *, system, user, schema, max_tokens):
        return LLMResult(parsed=self.draft, provider="fake:test")


@pytest.fixture
def world(db):
    officer = User(email="o@p.test", password_hash="!", name="Officer", role="gov_admin")
    citizen = User(email="c@p.test", password_hash="!", name="Citizen", role="citizen")
    zone = Zone(name="Akkalkot taluka, Solapur", hazard="drought", zone_type="taluka", status="active", score=79,
                population_est=381611, population_urban=81621, geom=from_shape(box(76.0, 17.3, 76.4, 17.7), srid=4326),
                centroid=from_shape(Point(76.2, 17.5), srid=4326))
    db.add_all([officer, citizen, zone])
    db.flush()
    return db, zone, officer, citizen


def service(db, draft):
    return PlanService(PlanRepository(db), FakeLLM(draft), trend=lambda zone_id: TREND)


def test_a_plan_has_ai_words_menu_options_and_code_costs(world):
    db, zone, officer, _ = world
    draft = PlanDraft(title="Make Akkalkot drought-proof by 2030",
                      problem_summary="Rains have failed for two seasons. Groundwater keeps falling. 80% of wells are dry.",
                      option_keys=["farm_ponds", "teleporters", "check_dams"])
    plan = service(db, draft).draft(zone.id, officer)
    assert plan["title"] == "Long-term water plan for Akkalkot taluka, Solapur"  # an invented year is a number too
    assert plan["problem_summary"] == "Rains have failed for two seasons. Groundwater keeps falling."
    assert [o["key"] for o in plan["options"]] == ["farm_ponds", "check_dams"]
    assert plan["total_cost_inr"] == sum(o["cost_inr"] for o in plan["options"])
    assert plan["trend"]["first_score"] == 40.0 and plan["trend"]["last_score"] == 79.0
    assert plan["status"] == "draft" and plan["written_by"] == "fake:test"


def test_without_the_ai_a_plain_plan_with_default_options_is_drafted(world):
    db, zone, officer, _ = world
    plan = service(db, None).draft(zone.id, officer)
    assert plan["written_by"] == "template" and len(plan["options"]) == 3 and plan["total_cost_inr"] > 0


def test_only_officers_draft_and_review_and_drafts_stay_private(world):
    db, zone, officer, citizen = world
    svc = service(db, None)
    with pytest.raises(ForbiddenError):
        svc.draft(zone.id, citizen)
    plan = svc.draft(zone.id, officer)
    assert svc.latest_for_zone(zone.id, viewer=citizen) is None
    with pytest.raises(NotFoundError):
        svc.get(plan["id"], viewer=None)
    svc.approve(plan["id"], officer)
    assert svc.get(plan["id"], viewer=None)["status"] == "approved"
    with pytest.raises(ConflictError):
        svc.reject(plan["id"], officer, "late")
