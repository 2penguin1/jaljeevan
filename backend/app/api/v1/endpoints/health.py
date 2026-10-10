from fastapi import APIRouter

from app.api.dependencies import SessionDep
from app.core.config import settings
from app.repositories import system_repository
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: SessionDep) -> HealthResponse:
    return HealthResponse(ok=True, app=settings.app_name, postgis=system_repository.postgis_version(db))
