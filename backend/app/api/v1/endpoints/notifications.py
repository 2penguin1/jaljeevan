"""A logged-in user's own notifications (never anyone else's)."""
from fastapi import APIRouter

from app.api.dependencies import CurrentUser, SessionDep
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notifications import MarkReadIn, NotificationsOut
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("")
def my_notifications(user: CurrentUser, db: SessionDep) -> NotificationsOut:
    return NotificationsOut(**NotificationService(NotificationRepository(db)).inbox(user.id))


@router.post("/read", status_code=204)
def mark_read(body: MarkReadIn, user: CurrentUser, db: SessionDep) -> None:
    NotificationService(NotificationRepository(db)).mark_read(user.id, body.ids)
    db.commit()
