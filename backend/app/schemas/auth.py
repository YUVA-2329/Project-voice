"""Authentication request/response bodies."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.users import UserOut


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("display_name must not be blank")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthResponse(BaseModel):
    user: UserOut


class CsrfResponse(BaseModel):
    csrf_token: str
