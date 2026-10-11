"""Login, logout, who am I, and citizen signup. Sessions live in an httpOnly cookie (scripts cannot read it)."""
from fastapi import APIRouter, HTTPException, Response

from app.api.dependencies import CurrentUser, SessionDep
from app.core.config import settings
from app.core.security import COOKIE, TTL_SECONDS, LoginBrake, hash_password, issue_token, verify_password
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginIn, MeOut, SignupIn

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
brake = LoginBrake()  # per process: one API task in this deployment


def _me(user: User, users: UserRepository) -> MeOut:
    org = users.org(user.org_id)
    return MeOut(id=user.id, email=user.email, name=user.name, role=user.role, org_id=user.org_id,
                 org_name=org.name if org else None)


def _start_session(response: Response, user: User) -> None:
    response.set_cookie(COOKIE, issue_token(user.id, user.role, user.org_id), max_age=TTL_SECONDS, httponly=True,
                        samesite="lax", secure=settings.cookie_secure, path="/")


@router.post("/login")
def login(body: LoginIn, response: Response, db: SessionDep) -> MeOut:
    if not brake.allowed(body.email):
        raise HTTPException(status_code=429, detail="Too many wrong passwords. Try again in a minute")
    users = UserRepository(db)
    user = users.by_email(body.email)
    if user is None or not verify_password(body.password, user.password_hash):
        brake.failed(body.email)
        raise HTTPException(status_code=401, detail="Wrong email or password")
    _start_session(response, user)
    return _me(user, users)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="lax", secure=settings.cookie_secure)


@router.get("/me")
def me(user: CurrentUser, db: SessionDep) -> MeOut:
    return _me(user, UserRepository(db))


@router.post("/signup", status_code=201)
def signup(body: SignupIn, response: Response, db: SessionDep) -> MeOut:
    users = UserRepository(db)
    if users.by_email(body.email) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = users.add(User(email=body.email.lower(), name=body.name, password_hash=hash_password(body.password),
                          role="citizen", org_id=None))
    db.commit()
    _start_session(response, user)
    return _me(user, users)
