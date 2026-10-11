"""Relief tenders: from a zone's water need to invited vendors and an agreed supply.

Every number is computed here (the AI writes no numbers); the negotiation rules live in domain/bids.py. Who may act is
decided by the logged-in account, never by the request: a relief officer acts for the government, a vendor account only
on its own company's bid. Each bid action carries the version it saw, so two people never silently overwrite each other.
"""
import uuid
from datetime import datetime, timezone

from app.core.exceptions import ConflictError, DomainValidationError, ForbiddenError, NotFoundError
from app.domain.bids import BidRules
from app.domain.matching import Vendor, match_vendors, suggested_price
from app.domain.relief import ReliefNeed, relief_need
from app.models import Bid, BidMessage, BidOffer, Tender, User
from app.repositories.tender_repository import TenderRepository

SIDE_NAME = {"gov": "Government", "vendor": "Vendor"}
OPEN = ("invited", "countered")


class TenderService:
    def __init__(self, repo: TenderRepository, rules: BidRules | None = None):
        self.repo = repo
        self.rules = rules or BidRules()

    # -- reads ----------------------------------------------------------------------------------------------------
    def relief_need(self, zone_id: uuid.UUID, share: float = 0.10) -> ReliefNeed:
        zone = self._zone(zone_id)
        if not 0 < share <= 1:
            raise DomainValidationError("share must be between 0 and 1")
        return relief_need(zone.population_est, zone.population_urban, share)

    def suggested_price(self, zone_id: uuid.UUID, radius_km: float) -> float:
        return suggested_price(self._matches(zone_id, radius_km, need_kl_per_day=1))

    def vendors(self) -> list[dict]:
        return [{"id": o.id, "name": o.name, "state_code": o.state_code, "tanker_count": o.tanker_count,
                 "price_per_kl": o.base_price_per_kl, "reliability": o.reliability} for o, _, _ in self.repo.vendors()]

    def tenders(self) -> list[dict]:
        return [self._summary(t) for t in self.repo.tenders()]

    def detail(self, tender_id: uuid.UUID) -> dict:
        tender = self._tender(tender_id)
        out = self._summary(tender)
        out["bids"] = [self._bid(bid) for bid in self.repo.bids(tender.id)]
        return out

    def inbox(self, actor: User) -> dict:
        """A vendor's bids by whose move it is: needs your action / waiting for the government / closed."""
        if actor.role != "vendor" or actor.org_id is None:
            raise ForbiddenError("only vendor accounts have an inbox")
        buckets: dict[str, list] = {"needs_action": [], "waiting": [], "closed": []}
        for bid in self.repo.bids_for_vendor(actor.org_id):
            tender = self.repo.get(bid.tender_id)
            zone = self.repo.zone(tender.zone_id) if tender else None
            item = {**self._bid(bid, with_messages=False), "tender_id": bid.tender_id,
                    "zone_name": zone.name if zone else "?", "duration_days": tender.duration_days if tender else 0}
            key = "closed" if bid.status not in OPEN else ("needs_action" if bid.turn == "vendor" else "waiting")
            buckets[key].append(item)
        return buckets

    # -- writes ---------------------------------------------------------------------------------------------------
    def create(self, zone_id: uuid.UUID, qty_per_day: float, duration_days: int, price_per_unit: float,
               radius_km: float, actor: User) -> uuid.UUID:
        """Publish a water-tanker tender for a zone and invite the best vendors in reach, each with an opening offer
        (the tender price, for as much as the vendor's fleet can carry a day, up to the need)."""
        self._officer(actor)
        if qty_per_day <= 0 or duration_days <= 0 or price_per_unit <= 0 or radius_km <= 0:
            raise DomainValidationError("quantity, days, price and radius must be positive")
        zone = self._zone(zone_id)
        tender = self.repo.add(Tender(zone_id=zone.id, gov_org_id=actor.org_id, created_by=actor.id,
                                      qty_per_day=qty_per_day, duration_days=duration_days,
                                      price_per_unit=price_per_unit, radius_km=radius_km, status="published",
                                      published_at=datetime.now(timezone.utc)))
        for match in self._matches(zone.id, radius_km, qty_per_day):
            vendor = match.vendor
            bid = self.repo.add(Bid(tender_id=tender.id, vendor_org_id=vendor.key, distance_km=match.road_km,
                                    rank_score=match.score, rank_reason=match.reason, status="invited", turn="vendor",
                                    current_offer_version=1))
            qty = min(qty_per_day, vendor.tanker_count * vendor.capacity_kl)
            offer = self.repo.add(BidOffer(bid_id=bid.id, version=1, price_per_unit=price_per_unit, qty_per_day=qty,
                                           proposed_by_side="gov", proposed_by=actor.id))
            self.repo.add(BidMessage(created_at=datetime.now(timezone.utc), bid_id=bid.id, side="system", offer_id=offer.id,
                                     body=f"Invited: {match.reason}. Opening offer {qty:g} kL a day at "
                                          f"₹{price_per_unit:g}/kL for {duration_days} days."))
        return tender.id

    def act(self, tender_id: uuid.UUID, bid_id: uuid.UUID, actor: User, action: str, expected_version: int,
            price_per_unit: float | None = None, qty_per_day: float | None = None, note: str | None = None) -> None:
        tender = self._tender(tender_id)
        bid = self._bid_row(tender, bid_id)
        side = self._side(actor, bid)
        if bid.version != expected_version:
            raise ConflictError("This bid changed. Reload to see the latest offer.")
        status, turn = self.rules.next(bid.status, bid.turn, side, action)
        latest = self.repo.offers(bid.id)[-1]
        if action == "counter":
            if not price_per_unit or not qty_per_day or price_per_unit <= 0 or qty_per_day <= 0:
                raise DomainValidationError("a counter needs a positive price and quantity")
            latest.status = "superseded"
            offer = self.repo.add(BidOffer(bid_id=bid.id, version=latest.version + 1, price_per_unit=price_per_unit,
                                           qty_per_day=qty_per_day, proposed_by_side=side, proposed_by=actor.id,
                                           note=note))
            bid.current_offer_version = offer.version
            body = f"{SIDE_NAME[side]} countered: {qty_per_day:g} kL a day at ₹{price_per_unit:g}/kL"
            body += f": “{note}”" if note else ""
        elif action == "accept":
            offer, offer.status = latest, "agreed"
            body = (f"{SIDE_NAME[side]} accepted: {latest.qty_per_day:g} kL a day at ₹{latest.price_per_unit:g}/kL "
                    f"for {tender.duration_days} days")
        else:
            offer, offer.status = latest, "rejected"
            body = f"{SIDE_NAME[side]} declined" + (f" ({note})" if note else "")
        bid.status, bid.turn, bid.version = status, turn, bid.version + 1
        self.repo.add(BidMessage(created_at=datetime.now(timezone.utc), bid_id=bid.id, side="system", body=body, offer_id=offer.id))

    def message(self, tender_id: uuid.UUID, bid_id: uuid.UUID, actor: User, body: str) -> None:
        """A note in the bid thread from either party; whose turn it is does not change."""
        bid = self._bid_row(self._tender(tender_id), bid_id)
        side = self._side(actor, bid)
        text = (body or "").strip()
        if not text:
            raise DomainValidationError("a message cannot be empty")
        self.repo.add(BidMessage(created_at=datetime.now(timezone.utc), bid_id=bid.id, side=side, author_id=actor.id, body=text[:1000]))

    def raise_price(self, tender_id: uuid.UUID, actor: User, price_per_unit: float) -> None:
        """A higher government price for every open bid: a new offer each, and it is the vendors' move again."""
        self._officer(actor)
        tender = self._tender(tender_id)
        if price_per_unit <= tender.price_per_unit:
            raise ConflictError(f"the new price must be higher than ₹{tender.price_per_unit:g}/kL")
        for bid in self.repo.bids(tender.id):
            if bid.status not in OPEN:
                continue
            latest = self.repo.offers(bid.id)[-1]
            latest.status = "superseded"
            offer = self.repo.add(BidOffer(bid_id=bid.id, version=latest.version + 1, price_per_unit=price_per_unit,
                                           qty_per_day=latest.qty_per_day, proposed_by_side="gov", proposed_by=actor.id))
            bid.current_offer_version, bid.turn, bid.version = offer.version, "vendor", bid.version + 1
            self.repo.add(BidMessage(created_at=datetime.now(timezone.utc), bid_id=bid.id, side="system", offer_id=offer.id,
                                     body=f"Government raised the price to ₹{price_per_unit:g}/kL "
                                          f"for {latest.qty_per_day:g} kL a day"))
        tender.price_per_unit = price_per_unit
        tender.version += 1

    # -- helpers --------------------------------------------------------------------------------------------------
    @staticmethod
    def _officer(actor: User) -> None:
        if actor.role != "gov_admin":
            raise ForbiddenError("only a relief officer can do this")

    @staticmethod
    def _side(actor: User, bid: Bid) -> str:
        if actor.role == "gov_admin":
            return "gov"
        if actor.role == "vendor" and actor.org_id == bid.vendor_org_id:
            return "vendor"
        raise ForbiddenError("this bid belongs to another company")

    def _bid(self, bid: Bid, with_messages: bool = True) -> dict:
        offers = self.repo.offers(bid.id)
        latest = offers[-1] if offers else None
        vendor = self.repo.org(bid.vendor_org_id)
        out = {"id": bid.id, "vendor_id": bid.vendor_org_id, "vendor_name": vendor.name if vendor else "?",
               "distance_km": bid.distance_km, "rank_score": bid.rank_score, "reason": bid.rank_reason,
               "status": bid.status, "turn": bid.turn, "version": bid.version,
               "offer": None if latest is None else {
                   "version": latest.version, "price_per_unit": latest.price_per_unit,
                   "qty_per_day": latest.qty_per_day, "proposed_by_side": latest.proposed_by_side,
                   "status": latest.status, "note": latest.note},
               "messages": []}
        if with_messages:
            messages = self.repo.messages(bid.id)
            names = self.repo.user_names({m.author_id for m in messages if m.author_id})
            out["messages"] = [{"side": m.side, "body": m.body, "at": m.created_at,
                                "author": names.get(m.author_id) if m.author_id else None} for m in messages]
        return out

    def _summary(self, tender: Tender) -> dict:
        zone = self.repo.zone(tender.zone_id)
        bids = self.repo.bids(tender.id)
        committed = sum(o.qty_per_day for b in bids for o in self.repo.offers(b.id) if o.status == "agreed")
        return {"id": tender.id, "zone_id": tender.zone_id, "zone_name": zone.name if zone else "?",
                "status": tender.status, "qty_per_day": tender.qty_per_day, "duration_days": tender.duration_days,
                "price_per_unit": tender.price_per_unit, "radius_km": tender.radius_km,
                "published_at": tender.published_at, "committed_kl_per_day": committed,
                "waiting_for_gov": sum(1 for b in bids if b.status in OPEN and b.turn == "gov")}

    def _matches(self, zone_id: uuid.UUID, radius_km: float, need_kl_per_day: float):
        point = self.repo.zone_point(zone_id)
        if point is None:
            raise NotFoundError(f"zone {zone_id} has no location")
        vendors = [Vendor(o.id, lat, lon, o.tanker_count, o.tanker_capacity_kl, o.base_price_per_kl or 60.0,
                          o.reliability) for o, lat, lon in self.repo.vendors()]
        return match_vendors(point, vendors, radius_km, need_kl_per_day)

    def _bid_row(self, tender: Tender, bid_id: uuid.UUID) -> Bid:
        bid = self.repo.bid(tender.id, bid_id)
        if bid is None:
            raise NotFoundError(f"bid {bid_id} not found on this tender")
        return bid

    def _zone(self, zone_id: uuid.UUID):
        zone = self.repo.zone(zone_id)
        if zone is None:
            raise NotFoundError(f"zone {zone_id} not found")
        return zone

    def _tender(self, tender_id: uuid.UUID) -> Tender:
        tender = self.repo.get(tender_id)
        if tender is None:
            raise NotFoundError(f"tender {tender_id} not found")
        return tender
