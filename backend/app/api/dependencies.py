import secrets
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.container import Container
from app.core.database import get_db
from app.core.security import InvalidToken, read_token
from app.models import User

SessionDep = Annotated[Session, Depends(get_db)]


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]


def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
    configured = settings.admin_token
    if not configured or not x_admin_token or not secrets.compare_digest(x_admin_token, configured):
        raise HTTPException(status_code=401, detail="admin token required")


def current_user(db: SessionDep, session: Annotated[str | None, Cookie()] = None) -> User:
    """The logged-in user, from the httpOnly session cookie. 401 when missing, forged, expired or deleted."""
    if not session:
        raise HTTPException(status_code=401, detail="Please log in")
    try:
        claims = read_token(session)
    except InvalidToken:
        raise HTTPException(status_code=401, detail="Your session has ended. Please log in again") from None
    user = db.get(User, claims.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_role(*roles: str):
    """Dependency factory: the logged-in user must have one of `roles` (403 otherwise)."""
    def check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Your account cannot do this")
        return user
    return check


def optional_user(db: SessionDep, session: Annotated[str | None, Cookie()] = None) -> User | None:
    """The logged-in user if there is a valid session, else None (for pages anyone may read)."""
    if not session:
        return None
    try:
        return db.get(User, read_token(session).user_id)
    except InvalidToken:
        return None


MaybeUser = Annotated[User | None, Depends(optional_user)]
