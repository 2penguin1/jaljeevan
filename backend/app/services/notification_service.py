"""Private in-app notifications: who should hear about a tender event, never the person who caused it."""
import uuid
from datetime import datetime, timezone

from app.models import Notification
from app.repositories.notification_repository import NotificationRepository


class NotificationService:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    def tell_org(self, org_id: uuid.UUID | None, kind: str, text: str, tender_id: uuid.UUID,
                 actor_id: uuid.UUID | None) -> None:
        now = datetime.now(timezone.utc)
        payload = {"tender_id": str(tender_id), "text": text[:300], "link": f"/tenders/{tender_id}"}
        self.repo.add_all([Notification(user_id=uid, kind=kind, payload=payload, created_at=now)
                           for uid in self.repo.org_user_ids(org_id) if uid != actor_id])

    def inbox(self, user_id: uuid.UUID) -> dict:
        return {"unread": self.repo.unread_count(user_id),
                "items": [{"id": n.id, "kind": n.kind, "text": n.payload.get("text", ""),
                           "link": n.payload.get("link"), "created_at": n.created_at, "read": n.read_at is not None}
                          for n in self.repo.latest(user_id)]}

    def mark_read(self, user_id: uuid.UUID, ids: list[uuid.UUID] | None) -> None:
        self.repo.mark_read(user_id, ids)
