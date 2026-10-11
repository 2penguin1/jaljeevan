import uuid

from pydantic import BaseModel, EmailStr, Field


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class SignupIn(BaseModel):
    """Citizen signup. There is deliberately no role or organisation field: those are never chosen by the user."""
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: str
    org_id: uuid.UUID | None
    org_name: str | None
