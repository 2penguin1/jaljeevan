import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RunStarted(BaseModel):
    run_id: uuid.UUID


class PipelineRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    started_at: datetime
    finished_at: datetime | None
    stats: dict
