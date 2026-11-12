"""User and preference schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.common import ApiModel, LanguageOrAuto, OutputFormat


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_language: LanguageOrAuto = "auto"
    default_engine: str | None = None
    output_format: OutputFormat = "wav"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    theme: Literal["system", "light", "dark"] = "system"
    mode: Literal["simple", "advanced"] = "simple"


class PreferencesPatch(BaseModel):
    """All optional: merged onto the stored preferences."""

    model_config = ConfigDict(extra="forbid")

    default_language: LanguageOrAuto | None = None
    default_engine: str | None = None
    output_format: OutputFormat | None = None
    speed: float | None = Field(default=None, ge=0.5, le=2.0)
    theme: Literal["system", "light", "dark"] | None = None
    mode: Literal["simple", "advanced"] | None = None


class UserOut(ApiModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    created_at: datetime
    preferences: Preferences

    @field_validator("preferences", mode="before")
    @classmethod
    def _coerce_preferences(cls, value: Any) -> Any:
        if isinstance(value, dict):
            # Fill any missing key with defaults so older rows always serialise completely.
            return Preferences.model_validate({**Preferences().model_dump(), **value})
        return value


class UserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    preferences: PreferencesPatch | None = None


class UserDelete(BaseModel):
    password: str = Field(min_length=1, max_length=128)
