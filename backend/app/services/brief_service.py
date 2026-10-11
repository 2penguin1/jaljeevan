"""Relief briefs: the AI writes the words, code writes every number, and a relief officer approves or rejects.

Draft: numbers come from code (relief need, nearby vendor prices, budget = kL a day x days x price). The AI gets those
numbers and the zone's evidence as facts and returns a short situation summary, actions picked from the hazard's fixed
playbook, and the evidence it relied on. Code then keeps only actions from the playbook, citations from this zone, and
sentences without digits. If the AI is unavailable, a plain template summary is used: a brief can always be drafted.
Approve publishes the prefilled tender in the same step.
"""
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.core.exceptions import ConflictError, DomainValidationError, ForbiddenError, NotFoundError
from app.domain.playbook import PLAYBOOK, keep_actions, without_numbers
from app.integrations.ports import LLMClient
from app.models import ReliefBrief, User
from app.repositories.brief_repository import BriefRepository
from app.repositories.tender_repository import TenderRepository
from app.services.tender_service import TenderService

LOG = logging.getLogger(__name__)
DURATION_DAYS = 30
RADIUS_KM = 100
TANKER_SHARE = 0.10
MAX_EVIDENCE = 8


class BriefDraft(BaseModel):
    """What the AI may write. No number fields on purpose."""
    situation: str = Field(description="3-5 short plain-English sentences about the situation, with no numbers")
    action_keys: list[str] = Field(description="keys chosen from the playbook, most urgent first")
    cited_signal_ids: list[str] = Field(description="ids of the evidence posts the summary relies on")


SYSTEM = (
    "You write short relief briefs for Indian district officials. Use only the facts and evidence given. "
    "Write plain English with no numbers at all (the numbers are shown separately). Pick actions only from the "
    "playbook keys given. Cite the ids of the evidence you used. If evidence is thin, say so plainly.")


class BriefService:
    def __init__(self, briefs: BriefRepository, tenders_repo: TenderRepository, tenders: TenderService,
                 llm: LLMClient | None, evidence: Callable[[uuid.UUID], list[dict]]):
        self.briefs = briefs
        self.tenders_repo = tenders_repo
        self.tenders = tenders
        self.llm = llm
        self.evidence = evidence

    # -- reads ----------------------------------------------------------------------------------------------------
    def get(self, brief_id: uuid.UUID, viewer: User | None) -> dict:
        brief = self.briefs.get(brief_id)
        if brief is None or (brief.status != "approved" and not self._is_officer(viewer)):
            raise NotFoundError(f"brief {brief_id} not found")  # drafts are not public: same answer as missing
        return self._out(brief)

    def latest_for_zone(self, zone_id: uuid.UUID, viewer: User | None) -> dict | None:
        statuses = ("draft", "approved", "rejected") if self._is_officer(viewer) else ("approved",)
        brief = self.briefs.latest(zone_id, statuses)
        return self._out(brief) if brief else None

    def queue(self, actor: User) -> list[dict]:
        self._officer(actor)
        return [self._out(b) for b in self.briefs.with_status("draft")]

    # -- writes ---------------------------------------------------------------------------------------------------
    def draft(self, zone_id: uuid.UUID, actor: User) -> dict:
        self._officer(actor)
        zone = self.tenders_repo.zone(zone_id)
        if zone is None:
            raise NotFoundError(f"zone {zone_id} not found")
        need = self.tenders.relief_need(zone_id, TANKER_SHARE)
        if need.kl_per_day <= 0:
            raise DomainValidationError("this zone has no population estimate yet, so its water need cannot be sized")
        price = self.tenders.suggested_price(zone_id, RADIUS_KM)
        budget = round(need.kl_per_day * DURATION_DAYS * price)
        evidence = self.evidence(zone_id)[:MAX_EVIDENCE]
        hazard = zone.hazard if zone.hazard in PLAYBOOK else "drought"
        written_by, situation, actions, cited = "template", "", [], []
        if self.llm is not None:
            try:
                result = self.llm.parse(system=SYSTEM, user=self._prompt(zone.name, hazard, need, price, budget, evidence),
                                        schema=BriefDraft, max_tokens=900)
                if result.parsed is not None:
                    draft: BriefDraft = result.parsed  # type: ignore[assignment]
                    situation = without_numbers(draft.situation)
                    actions = keep_actions(hazard, draft.action_keys)
                    allowed = {str(e["signal_id"]) for e in evidence}
                    cited = list(dict.fromkeys(i for i in draft.cited_signal_ids if i in allowed))
                    written_by = result.provider or "ai"
            except Exception:  # noqa: BLE001 - any AI failure falls back to the template; numbers never depend on it
                LOG.exception("brief AI failed; using the template")
        if not situation:
            written_by = "template"
            situation = (f"Measured data and {'local reports' if evidence else 'no local reports yet'} show a "
                         f"drinking-water shortage in {zone.name}. The numbers below are computed from the people "
                         f"living in the dry parts and nearby tanker prices.")
            situation = without_numbers(situation)
        if not actions:
            actions = list(PLAYBOOK[hazard])[:3]
        brief = self.briefs.add(ReliefBrief(
            zone_id=zone.id, version=self.briefs.next_version(zone.id), status="draft", summary=situation,
            cited_signal_ids=cited, population_est=need.people, lpcd_norm=20, need_per_day=need.kl_per_day,
            unit="kl", units_per_day=need.tanker_trips_per_day, duration_days=DURATION_DAYS, budget_inr=budget,
            suggested_price_per_unit=price,
            price_basis={"rule": f"median price of tanker vendors within {RADIUS_KM} km", "formula": need.formula,
                         "written_by": written_by},
            short_term=actions, long_term=[]))
        return self._out(brief)

    def approve(self, brief_id: uuid.UUID, actor: User) -> uuid.UUID:
        """Approve a draft and publish its prefilled tender in one step. Returns the tender id."""
        self._officer(actor)
        brief = self._draft_for_update(brief_id)
        tender_id = self.tenders.create(brief.zone_id, brief.need_per_day, brief.duration_days,
                                        brief.suggested_price_per_unit, RADIUS_KM, actor=actor)
        self.tenders_repo.get(tender_id).brief_id = brief.id
        brief.status, brief.reviewed_by, brief.reviewed_at = "approved", actor.id, datetime.now(timezone.utc)
        return tender_id

    def reject(self, brief_id: uuid.UUID, actor: User, notes: str) -> None:
        self._officer(actor)
        brief = self._draft_for_update(brief_id)
        brief.status, brief.reviewed_by, brief.reviewed_at = "rejected", actor.id, datetime.now(timezone.utc)
        brief.review_notes = (notes or "").strip()[:500] or None

    # -- helpers --------------------------------------------------------------------------------------------------
    def _draft_for_update(self, brief_id: uuid.UUID) -> ReliefBrief:
        brief = self.briefs.for_update(brief_id)
        if brief is None:
            raise NotFoundError(f"brief {brief_id} not found")
        if brief.status != "draft":
            raise ConflictError(f"this brief is already {brief.status}")
        return brief

    @staticmethod
    def _prompt(zone: str, hazard: str, need, price: float, budget: int, evidence: list[dict]) -> str:
        playbook = "\n".join(f"- {key}: {text}" for key, text in PLAYBOOK[hazard].items())
        posts = "\n".join(f"[{e['signal_id']}] {e.get('place') or ''}: \"{e.get('quote') or ''}\" ({e.get('summary') or ''})"
                          for e in evidence) or "(no posts linked to this zone yet)"
        return (f"Zone: {zone} (hazard: {hazard})\n"
                f"Facts computed by code (do not repeat numbers): {need.formula}; suggested tanker price "
                f"{price:g} rupees per kL; 30-day budget {budget} rupees.\n"
                f"Evidence posts:\n{posts}\n\nPlaybook keys:\n{playbook}")

    @staticmethod
    def _is_officer(viewer: User | None) -> bool:
        return viewer is not None and viewer.role == "gov_admin"

    def _officer(self, actor: User) -> None:
        if not self._is_officer(actor):
            raise ForbiddenError("only a relief officer can do this")

    def _out(self, brief: ReliefBrief) -> dict:
        zone = self.tenders_repo.zone(brief.zone_id)
        hazard = zone.hazard if zone and zone.hazard in PLAYBOOK else "drought"
        return {"id": brief.id, "zone_id": brief.zone_id, "zone_name": zone.name if zone else "?",
                "version": brief.version, "status": brief.status, "summary": brief.summary,
                "actions": [{"key": k, "text": PLAYBOOK[hazard].get(k, k)} for k in brief.short_term or []],
                "cited_signal_ids": list(brief.cited_signal_ids or []), "people": brief.population_est,
                "need_per_day": brief.need_per_day, "units_per_day": brief.units_per_day,
                "duration_days": brief.duration_days, "budget_inr": brief.budget_inr,
                "suggested_price_per_unit": brief.suggested_price_per_unit,
                "formula": (brief.price_basis or {}).get("formula", ""),
                "written_by": (brief.price_basis or {}).get("written_by", ""),
                "review_notes": brief.review_notes, "created_at": brief.created_at}
