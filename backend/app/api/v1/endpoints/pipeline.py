import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends

from app.api.dependencies import ContainerDep, SessionDep, require_admin
from app.core.exceptions import NotFoundError
from app.repositories.pipeline_run_repository import PipelineRunRepository
from app.schemas.pipeline import PipelineRunOut, RunStarted

router = APIRouter(prefix="/admin/pipeline", tags=["pipeline"], dependencies=[Depends(require_admin)])


@router.post("/run", status_code=202)
def trigger_run(db: SessionDep, container: ContainerDep, background: BackgroundTasks) -> RunStarted:
    """Start a full pipeline run in the background; poll GET /runs/{id} for its stats."""
    run = PipelineRunRepository(db).start("local", datetime.now(timezone.utc))
    db.commit()  # the background job must see this row
    background.add_task(container.run_pipeline_job, run.id)
    return RunStarted(run_id=run.id)


@router.get("/runs")
def list_runs(db: SessionDep) -> list[PipelineRunOut]:
    return [PipelineRunOut.model_validate(r) for r in PipelineRunRepository(db).latest()]


@router.get("/runs/{run_id}")
def get_run(run_id: uuid.UUID, db: SessionDep) -> PipelineRunOut:
    run = PipelineRunRepository(db).find(run_id)
    if run is None:
        raise NotFoundError(f"pipeline run {run_id} not found")
    return PipelineRunOut.model_validate(run)
