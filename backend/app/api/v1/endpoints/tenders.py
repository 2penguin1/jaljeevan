"""Relief tenders. Reading is open to everyone; every write needs the demo access code (X-Admin-Token)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import ContainerDep, SessionDep, require_admin
from app.schemas.tenders import (BidActionIn, ReliefNeedOut, TenderCreated, TenderDetail, TenderIn, TenderSummary,
                                 VendorOut)

router = APIRouter(prefix="/api/v1", tags=["tenders"])
WRITE = [Depends(require_admin)]


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
def tender_detail(tender_id: uuid.UUID, db: SessionDep, container: ContainerDep) -> TenderDetail:
    return TenderDetail(**container.tender_service(db).detail(tender_id))


@router.post("/tenders", status_code=201, dependencies=WRITE)
def create_tender(body: TenderIn, db: SessionDep, container: ContainerDep) -> TenderCreated:
    tender_id = container.tender_service(db).create(body.zone_id, body.qty_per_day, body.duration_days,
                                                    body.price_per_unit, body.radius_km)
    db.commit()
    return TenderCreated(id=tender_id)


@router.post("/tenders/{tender_id}/bids/{bid_id}/actions", dependencies=WRITE)
def bid_action(tender_id: uuid.UUID, bid_id: uuid.UUID, body: BidActionIn, db: SessionDep,
               container: ContainerDep) -> TenderDetail:
    service = container.tender_service(db)
    service.act(tender_id, bid_id, body.side, body.action, body.price_per_unit, body.qty_per_day, body.note)
    db.commit()
    return TenderDetail(**service.detail(tender_id))


@router.get("/vendors")
def vendors(db: SessionDep, container: ContainerDep) -> list[VendorOut]:
    return [VendorOut(**v) for v in container.tender_service(db).vendors()]
