import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.container import Container
from app.core.database import get_db

SessionDep = Annotated[Session, Depends(get_db)]


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]


def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
    configured = settings.admin_token
    if not configured or not x_admin_token or not secrets.compare_digest(x_admin_token, configured):
        raise HTTPException(status_code=401, detail="admin token required")
