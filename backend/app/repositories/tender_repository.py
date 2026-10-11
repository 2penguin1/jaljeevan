import uuid

from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import select

from app.models import Bid, BidMessage, BidOffer, Organization, Tender, User, Zone
from app.repositories.base import BaseRepository


class TenderRepository(BaseRepository[Tender]):
    """Tenders, their bids, offers and messages, plus the organisations they involve. Flushes, never commits."""

    model = Tender

    def zone(self, zone_id: uuid.UUID) -> Zone | None:
        return self.session.get(Zone, zone_id)

    def zone_point(self, zone_id: uuid.UUID) -> tuple[float, float] | None:
        """(lat, lon) of the zone's centre."""
        row = self.session.execute(select(ST_Y(Zone.centroid), ST_X(Zone.centroid)).where(Zone.id == zone_id)).first()
        return (row[0], row[1]) if row and row[0] is not None else None

    def vendors(self) -> list[tuple[Organization, float, float]]:
        rows = self.session.execute(select(Organization, ST_Y(Organization.geom), ST_X(Organization.geom))
                                    .where(Organization.kind == "vendor", Organization.geom.isnot(None))
                                    .order_by(Organization.name)).all()
        return [(o, lat, lon) for o, lat, lon in rows]

    def government(self) -> tuple[Organization, User] | None:
        row = self.session.execute(select(Organization, User).join(User, User.org_id == Organization.id)
                                   .where(Organization.kind == "government").limit(1)).first()
        return (row[0], row[1]) if row else None

    def org(self, org_id: uuid.UUID) -> Organization | None:
        return self.session.get(Organization, org_id)

    def tenders(self) -> list[Tender]:
        return list(self.session.scalars(select(Tender).order_by(Tender.created_at.desc())))

    def bids(self, tender_id: uuid.UUID) -> list[Bid]:
        return list(self.session.scalars(select(Bid).where(Bid.tender_id == tender_id)
                                         .order_by(Bid.rank_score.desc())))

    def bid(self, tender_id: uuid.UUID, bid_id: uuid.UUID) -> Bid | None:
        return self.session.scalar(select(Bid).where(Bid.id == bid_id, Bid.tender_id == tender_id))

    def offers(self, bid_id: uuid.UUID) -> list[BidOffer]:
        return list(self.session.scalars(select(BidOffer).where(BidOffer.bid_id == bid_id)
                                         .order_by(BidOffer.version)))

    def messages(self, bid_id: uuid.UUID) -> list[BidMessage]:
        return list(self.session.scalars(select(BidMessage).where(BidMessage.bid_id == bid_id)
                                         .order_by(BidMessage.created_at, BidMessage.id)))
