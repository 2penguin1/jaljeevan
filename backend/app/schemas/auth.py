import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def _normal(cls, v: str) -> str:
        return v.strip().lower()  # one spelling per address, so the guessing brake cannot be dodged


class SignupIn(BaseModel):
    """Citizen signup. There is deliberately no role or organisation field: those are never chosen by the user."""
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=200)

    @field_validator("password")
    @classmethod
    def _fits_bcrypt(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Use a password of at most 72 bytes")
        return v


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: str
    org_id: uuid.UUID | None
    org_name: str | None
