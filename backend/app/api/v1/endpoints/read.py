import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.dependencies import ContainerDep, SessionDep
from app.schemas.read import FeedPage, OpsSummary, StatsOverview, ZoneDetail, ZoneSummary

router = APIRouter(prefix="/api/v1", tags=["read"])


@router.get("/feed")
def feed(db: SessionDep, container: ContainerDep, cursor: Annotated[str | None, Query(max_length=100)] = None,
         limit: Annotated[int, Query(ge=1, le=100)] = 50) -> FeedPage:
    """Relevant classified posts, newest first. Pass `next_cursor` back as `cursor` for the next page."""
    return container.read_query_service(db).feed(cursor, limit)


@router.get("/zones")
def zones(db: SessionDep, container: ContainerDep,
          hazard: Annotated[Literal["drought", "flood", "heat"] | None, Query()] = None,
          status: Annotated[Literal["watch", "active", "approved", "resolving"] | None, Query()] = None
          ) -> list[ZoneSummary]:
    return container.read_query_service(db).zones_list(hazard, status)


@router.get("/zones/{zone_id}")
def zone_detail(zone_id: uuid.UUID, db: SessionDep, container: ContainerDep) -> ZoneDetail:
    """One zone with the evidence and the arithmetic that put it on the map."""
    return container.read_query_service(db).zone_detail(zone_id)


@router.get("/stats/overview")
def stats_overview(db: SessionDep, container: ContainerDep) -> StatsOverview:
    return container.read_query_service(db).overview()


@router.get("/ops/summary")
def ops_summary(db: SessionDep, container: ContainerDep) -> OpsSummary:
    return container.read_query_service(db).ops()
