import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: uuid.UUID
    kind: str
    text: str
    link: str | None
    created_at: datetime
    read: bool


class NotificationsOut(BaseModel):
    unread: int
    items: list[NotificationOut]


class MarkReadIn(BaseModel):
    ids: list[uuid.UUID] | None = Field(default=None, max_length=200)  # none = all of mine
