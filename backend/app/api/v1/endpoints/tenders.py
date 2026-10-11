"""Relief tenders. Reading is open to everyone; writing needs a logged-in account with the right role."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import ContainerDep, MaybeUser, SessionDep, require_role
from app.models import User
from app.schemas.tenders import (BidActionIn, InboxOut, RaisePriceIn, ReliefNeedOut, TenderCreated, TenderDetail,
                                 TenderIn, TenderSummary, VendorOut)

router = APIRouter(prefix="/api/v1", tags=["tenders"])
Officer = Annotated[User, Depends(require_role("gov_admin"))]
Party = Annotated[User, Depends(require_role("gov_admin", "vendor"))]
VendorUser = Annotated[User, Depends(require_role("vendor"))]


@router.get("/zones/{zone_id}/relief-need")
def relief_need(zone_id: uuid.UUID, db: SessionDep, container: ContainerDep,
                share: Annotated[float, Query(gt=0, le=1)] = 0.10,
                radius_km: Annotated[float, Query(gt=0, le=500)] = 100) -> ReliefNeedOut:
    service = container.tender_service(db)
    need = service.relief_need(zone_id, share)
    return ReliefNeedOut(**need.__dict__, suggested_price=service.suggested_price(zone_id, radius_km))


@router.get("/tenders")
def list_tenders(db: SessionDep, container: ContainerDep) -> list[TenderSummary]:
    return [TenderSummary(**t) for t in container.tender_service(db).tenders()]


@router.get("/tenders/{tender_id}")
def tender_detail(tender_id: uuid.UUID, user: MaybeUser, db: SessionDep, container: ContainerDep) -> TenderDetail:
    return TenderDetail(**container.tender_service(db).detail(tender_id, viewer=user))


@router.post("/tenders", status_code=201)
def create_tender(body: TenderIn, user: Officer, db: SessionDep, container: ContainerDep) -> TenderCreated:
    tender_id = container.tender_service(db).create(body.zone_id, body.qty_per_day, body.duration_days,
                                                    body.price_per_unit, body.radius_km, actor=user)
    db.commit()
    return TenderCreated(id=tender_id)


@router.post("/tenders/{tender_id}/raise-price")
def raise_price(tender_id: uuid.UUID, body: RaisePriceIn, user: Officer, db: SessionDep,
                container: ContainerDep) -> TenderDetail:
    service = container.tender_service(db)
    service.raise_price(tender_id, user, body.price_per_unit)
    db.commit()
    return TenderDetail(**service.detail(tender_id, viewer=user))


@router.post("/tenders/{tender_id}/bids/{bid_id}/actions")
def bid_action(tender_id: uuid.UUID, bid_id: uuid.UUID, body: BidActionIn, user: Party, db: SessionDep,
               container: ContainerDep) -> TenderDetail:
    service = container.tender_service(db)
    if body.action == "message":
        service.message(tender_id, bid_id, user, body.body or "")
    else:
        if body.expected_version is None:
            raise HTTPException(status_code=422, detail="expected_version is required")
        service.act(tender_id, bid_id, user, body.action, body.expected_version, body.price_per_unit,
                    body.qty_per_day, body.note)
    db.commit()
    return TenderDetail(**service.detail(tender_id, viewer=user))


@router.get("/inbox")
def inbox(user: VendorUser, db: SessionDep, container: ContainerDep) -> InboxOut:
    return InboxOut(**container.tender_service(db).inbox(user))


@router.get("/vendors")
def vendors(db: SessionDep, container: ContainerDep) -> list[VendorOut]:
    return [VendorOut(**v) for v in container.tender_service(db).vendors()]
