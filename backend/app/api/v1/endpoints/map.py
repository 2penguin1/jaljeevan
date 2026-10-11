from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import ContainerDep, SessionDep
from app.schemas.read import Hazard

router = APIRouter(prefix="/api/v1/map", tags=["map"])

HazardQuery = Annotated[Hazard, Query()]


@router.get("/zones")
def map_zones(hazard: HazardQuery, db: SessionDep, container: ContainerDep) -> dict:
    """Live and watch zones for one hazard as a GeoJSON FeatureCollection."""
    return container.map_query_service(db).zones(hazard)


@router.get("/districts")
def map_districts(hazard: HazardQuery, db: SessionDep, container: ContainerDep) -> dict:
    """Every district with its latest indicator band for the hazard (cached for 10 minutes)."""
    return container.map_query_service(db).districts(hazard)


@router.get("/signals")
def map_signals(hazard: HazardQuery, db: SessionDep, container: ContainerDep,
                hours: Annotated[int, Query(ge=1, le=720)] = 48) -> dict:
    """Recent located posts (newest first, at most 1,000) as GeoJSON points."""
    return container.map_query_service(db).signals(hazard, hours)
