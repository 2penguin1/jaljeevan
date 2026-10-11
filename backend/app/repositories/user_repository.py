import uuid

from sqlalchemy import func, select

from app.models import Organization, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))

    def org(self, org_id: uuid.UUID | None) -> Organization | None:
        return self.session.get(Organization, org_id) if org_id else None
