from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Shared data-access helpers. Repositories flush but NEVER commit: the entry point owns the transaction."""

    model: type[ModelT]

    def __init__(self, session: Session):
        self.session = session

    def get(self, key: Any) -> ModelT | None:
        return self.session.get(self.model, key)

    def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        self.session.flush()
        return obj

    def add_all(self, objs: list[ModelT]) -> None:
        self.session.add_all(objs)
        self.session.flush()

    def list(self, limit: int = 100) -> list[ModelT]:
        return list(self.session.scalars(select(self.model).limit(limit)))
