"""Relief tenders: from a zone's water need to invited vendors and an agreed supply. Every number is computed here
(the AI writes no numbers); the negotiation rules live in domain/bids.py."""
import uuid
from datetime import datetime, timezone

from app.core.exceptions import DomainValidationError, NotFoundError
from app.domain.bids import BidRules
from app.domain.matching import Vendor, match_vendors, suggested_price
from app.domain.relief import ReliefNeed, relief_need
from app.models import Bid, BidMessage, BidOffer, Tender
from app.repositories.tender_repository import TenderRepository

SIDE_NAME = {"gov": "Government", "vendor": "Vendor"}


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
        bids = []
        for bid in self.repo.bids(tender.id):
            offers = self.repo.offers(bid.id)
            latest = offers[-1] if offers else None
            vendor = self.repo.org(bid.vendor_org_id)
            bids.append({"id": bid.id, "vendor_id": bid.vendor_org_id, "vendor_name": vendor.name if vendor else "?",
                         "distance_km": bid.distance_km, "rank_score": bid.rank_score, "reason": bid.rank_reason,
                         "status": bid.status, "turn": bid.turn,
                         "offer": None if latest is None else {
                             "version": latest.version, "price_per_unit": latest.price_per_unit,
                             "qty_per_day": latest.qty_per_day, "proposed_by_side": latest.proposed_by_side,
                             "status": latest.status, "note": latest.note},
                         "messages": [{"side": m.side, "body": m.body, "at": m.created_at}
                                      for m in self.repo.messages(bid.id)]})
        out["bids"] = bids
        return out

    # -- writes ---------------------------------------------------------------------------------------------------
    def create(self, zone_id: uuid.UUID, qty_per_day: float, duration_days: int, price_per_unit: float,
               radius_km: float) -> uuid.UUID:
        """Publish a water-tanker tender for a zone and invite the best vendors in reach, each with an opening offer
        (the tender price, for as much as the vendor's fleet can carry a day, up to the need)."""
        if qty_per_day <= 0 or duration_days <= 0 or price_per_unit <= 0 or radius_km <= 0:
            raise DomainValidationError("quantity, days, price and radius must be positive")
        zone = self._zone(zone_id)
        gov = self.repo.government()
        if gov is None:
            raise NotFoundError("no government office set up: run app.cli.seed_crm")
        org, officer = gov
        now = datetime.now(timezone.utc)
        tender = self.repo.add(Tender(zone_id=zone.id, gov_org_id=org.id, created_by=officer.id, qty_per_day=qty_per_day,
                                      duration_days=duration_days, price_per_unit=price_per_unit, radius_km=radius_km,
                                      status="published", published_at=now))
        for match in self._matches(zone.id, radius_km, qty_per_day):
            vendor = match.vendor
            bid = self.repo.add(Bid(tender_id=tender.id, vendor_org_id=vendor.key, distance_km=match.road_km,
                                    rank_score=match.score, rank_reason=match.reason, status="invited", turn="vendor",
                                    current_offer_version=1))
            qty = min(qty_per_day, vendor.tanker_count * vendor.capacity_kl)
            offer = self.repo.add(BidOffer(bid_id=bid.id, version=1, price_per_unit=price_per_unit, qty_per_day=qty,
                                           proposed_by_side="gov", proposed_by=officer.id))
            self.repo.add(BidMessage(bid_id=bid.id, side="system", offer_id=offer.id,
                                     body=f"Invited: {match.reason}. Opening offer {qty:g} kL a day at "
                                          f"₹{price_per_unit:g}/kL for {duration_days} days."))
        return tender.id

    def act(self, tender_id: uuid.UUID, bid_id: uuid.UUID, side: str, action: str,
            price_per_unit: float | None = None, qty_per_day: float | None = None, note: str | None = None) -> None:
        tender = self._tender(tender_id)
        bid = self.repo.bid(tender.id, bid_id)
        if bid is None:
            raise NotFoundError(f"bid {bid_id} not found on this tender")
        status, turn = self.rules.next(bid.status, bid.turn, side, action)
        offers = self.repo.offers(bid.id)
        latest = offers[-1]
        if action == "counter":
            if not price_per_unit or not qty_per_day or price_per_unit <= 0 or qty_per_day <= 0:
                raise DomainValidationError("a counter needs a positive price and quantity")
            latest.status = "superseded"
            new = self.repo.add(BidOffer(bid_id=bid.id, version=latest.version + 1, price_per_unit=price_per_unit,
                                         qty_per_day=qty_per_day, proposed_by_side=side, note=note))
            bid.current_offer_version = new.version
            body = f"{SIDE_NAME[side]} countered: {qty_per_day:g} kL a day at ₹{price_per_unit:g}/kL"
            offer_id = new.id
        elif action == "accept":
            latest.status = "agreed"
            body = (f"{SIDE_NAME[side]} accepted: {latest.qty_per_day:g} kL a day at ₹{latest.price_per_unit:g}/kL "
                    f"for {tender.duration_days} days")
            offer_id = latest.id
        else:
            latest.status = "rejected"
            body = f"{SIDE_NAME[side]} declined"
            offer_id = latest.id
        if note and action != "counter":
            body += f" ({note})"
        elif note:
            body += f": “{note}”"
        bid.status, bid.turn, bid.version = status, turn, bid.version + 1
        self.repo.add(BidMessage(bid_id=bid.id, side="system", body=body, offer_id=offer_id))

    # -- helpers --------------------------------------------------------------------------------------------------
    def _summary(self, tender: Tender) -> dict:
        zone = self.repo.zone(tender.zone_id)
        committed = sum(o.qty_per_day for b in self.repo.bids(tender.id) for o in self.repo.offers(b.id)
                        if o.status == "agreed")
        return {"id": tender.id, "zone_id": tender.zone_id, "zone_name": zone.name if zone else "?",
                "status": tender.status, "qty_per_day": tender.qty_per_day, "duration_days": tender.duration_days,
                "price_per_unit": tender.price_per_unit, "radius_km": tender.radius_km,
                "published_at": tender.published_at, "committed_kl_per_day": committed}

    def _matches(self, zone_id: uuid.UUID, radius_km: float, need_kl_per_day: float):
        point = self.repo.zone_point(zone_id)
        if point is None:
            raise NotFoundError(f"zone {zone_id} has no location")
        vendors = [Vendor(o.id, lat, lon, o.tanker_count, o.tanker_capacity_kl, o.base_price_per_kl or 60.0,
                          o.reliability) for o, lat, lon in self.repo.vendors()]
        return match_vendors(point, vendors, radius_km, need_kl_per_day)

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
