"""Long-term plans: options from a fixed menu, quantities and costs computed in code, words from the AI, and a relief
officer's approval. The trend section comes from the zone's own score history."""
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.core.exceptions import ConflictError, DomainValidationError, ForbiddenError, NotFoundError
from app.domain.plan_menu import MENU, plan_options, villages
from app.domain.playbook import without_numbers
from app.integrations.ports import LLMClient
from app.models import LongTermPlan, User
from app.repositories.plan_repository import PlanRepository
from app.services.ai_deadline import ask

LOG = logging.getLogger(__name__)
AI_DEADLINE_S = 20.0  # a person is waiting; CloudFront gives up at 60 s


class PlanDraft(BaseModel):
    """What the AI may write. No number fields on purpose."""
    title: str = Field(description="a short plan title with no numbers or years")
    problem_summary: str = Field(description="3-5 plain sentences on the long-term problem, with no numbers")
    option_keys: list[str] = Field(description="keys chosen from the menu, most useful first")


SYSTEM = ("You write long-term water-security plans for Indian district officials. Use only the facts given. Write "
          "plain English with no numbers, percentages or years (numbers are computed separately). Pick options only "
          "from the menu keys given.")


class PlanService:
    def __init__(self, plans: PlanRepository, llm: LLMClient | None, trend: Callable[[uuid.UUID], list[dict]]):
        self.plans = plans
        self.llm = llm
        self.trend = trend

    def get(self, plan_id: uuid.UUID, viewer: User | None) -> dict:
        plan = self.plans.get(plan_id)
        if plan is None or (plan.status != "approved" and not self._is_officer(viewer)):
            raise NotFoundError(f"plan {plan_id} not found")
        return self._out(plan)

    def latest_for_zone(self, zone_id: uuid.UUID, viewer: User | None) -> dict | None:
        statuses = ("draft", "approved", "rejected") if self._is_officer(viewer) else ("approved",)
        plan = self.plans.latest(zone_id, statuses)
        return self._out(plan) if plan else None

    def queue(self, actor: User) -> list[dict]:
        self._officer(actor)
        return [self._out(p) for p in self.plans.with_status("draft")]

    def draft(self, zone_id: uuid.UUID, actor: User) -> dict:
        self._officer(actor)
        zone = self.plans.zone(zone_id)
        if zone is None:
            raise NotFoundError(f"zone {zone_id} not found")
        open_draft = self.plans.latest(zone_id, ("draft",))
        if open_draft is not None:
            return self._out(open_draft)  # a double click (or a retry after a timeout) never makes a second draft
        hazard = zone.hazard if zone.hazard in MENU else "drought"
        rural = max(0, (zone.population_est or 0) - (zone.population_urban or 0))
        if rural <= 0:
            raise DomainValidationError("this zone has no population estimate yet, so a plan cannot be sized")
        points = self.trend(zone_id)
        trend = {"first_score": points[0]["score"] if points else None, "last_score": points[-1]["score"] if points else None,
                 "since": points[0]["at"].date().isoformat() if points else None, "points": len(points)}
        title, summary, keys, written_by = "", "", [], "template"
        menu = "\n".join(f"- {k}: {item.label}" for k, item in MENU[hazard].items())
        facts = (f"Zone: {zone.name} (hazard: {hazard}); about {villages(rural)} villages; score moved from "
                 f"{trend['first_score']} to {trend['last_score']} since {trend['since']}.")
        result = ask(self.llm, AI_DEADLINE_S, system=SYSTEM, user=f"{facts}\n\nMenu keys:\n{menu}", schema=PlanDraft,
                     max_tokens=900)
        if result is not None and result.parsed is not None:
            d: PlanDraft = result.parsed  # type: ignore[assignment]
            title, summary, keys = without_numbers(d.title), without_numbers(d.problem_summary), d.option_keys
            written_by = result.provider or "ai"
        options = plan_options(hazard, keys, rural) or plan_options(hazard, list(MENU[hazard])[:3], rural)
        if not summary:
            written_by = "template"
            summary = (f"{zone.name} keeps facing water stress. Storing monsoon water and recharging groundwater "
                       f"reduces how often tankers are needed.")
            summary = without_numbers(summary)
        plan = self.plans.add(LongTermPlan(
            zone_id=zone.id, hazard=hazard, version=self.plans.next_version(zone.id), status="draft",
            title=(title or f"Long-term water plan for {zone.name}")[:300], problem_summary=summary,
            trend={**trend, "written_by": written_by},
            options=[o.__dict__ for o in options], total_cost_inr=sum(o.cost_inr for o in options)))
        return self._out(plan)

    def approve(self, plan_id: uuid.UUID, actor: User) -> None:
        self._officer(actor)
        plan = self._draft_for_update(plan_id)
        plan.status, plan.reviewed_by = "approved", actor.id

    def reject(self, plan_id: uuid.UUID, actor: User, notes: str) -> None:
        self._officer(actor)
        plan = self._draft_for_update(plan_id)
        plan.status, plan.reviewed_by = "rejected", actor.id
        plan.review_notes = (notes or "").strip()[:500] or None

    def _draft_for_update(self, plan_id: uuid.UUID) -> LongTermPlan:
        plan = self.plans.for_update(plan_id)
        if plan is None:
            raise NotFoundError(f"plan {plan_id} not found")
        if plan.status != "draft":
            raise ConflictError(f"this plan is already {plan.status}")
        return plan

    @staticmethod
    def _is_officer(viewer: User | None) -> bool:
        return viewer is not None and viewer.role == "gov_admin"

    def _officer(self, actor: User) -> None:
        if not self._is_officer(actor):
            raise ForbiddenError("only a relief officer can do this")

    def _out(self, plan: LongTermPlan) -> dict:
        zone = self.plans.zone(plan.zone_id)
        trend = dict(plan.trend or {})
        return {"id": plan.id, "zone_id": plan.zone_id, "zone_name": zone.name if zone else "?", "hazard": plan.hazard,
                "version": plan.version, "status": plan.status, "title": plan.title,
                "problem_summary": plan.problem_summary, "options": list(plan.options or []),
                "total_cost_inr": plan.total_cost_inr, "written_by": trend.pop("written_by", ""),
                "trend": trend, "review_notes": plan.review_notes, "created_at": plan.created_at}
