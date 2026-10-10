import json
import uuid
from datetime import datetime

from sqlalchemy import select, text

from app.models import PipelineRun
from app.repositories.base import BaseRepository


class PipelineRunRepository(BaseRepository[PipelineRun]):
    model = PipelineRun

    def start(self, kind: str, at: datetime) -> PipelineRun:
        return self.add(PipelineRun(kind=kind, started_at=at))

    def finish(self, run: PipelineRun, stats: dict, at: datetime) -> None:
        run.stats = json.loads(json.dumps(stats, default=str))  # JSON-safe (UUIDs, datetimes)
        run.finished_at = at
        self.flush()

    def try_lock(self) -> bool:
        """Transaction-scoped advisory lock: only one pipeline run at a time across processes."""
        return bool(self.session.scalar(text("SELECT pg_try_advisory_xact_lock(hashtext('pipeline'))")))

    def savepoint(self):
        """Nested transaction (SAVEPOINT) the caller can commit or roll back without ending the job."""
        return self.session.begin_nested()

    def latest(self, limit: int = 20) -> list[PipelineRun]:
        return list(self.session.scalars(select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(limit)))

    def find(self, run_id: uuid.UUID) -> PipelineRun | None:
        return self.get(run_id)
