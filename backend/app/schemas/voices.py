"""Voice schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ApiModel, LanguageCode, LanguageOrAuto, ResourceError

VoiceStatusLiteral = Literal["processing", "ready", "failed", "consent_revoked"]


class VoiceReference(BaseModel):
    original_format: str
    duration_seconds: float
    sample_rate: int
    channels: int
    speech_seconds: float | None
    """Known once the reference has been processed (VAD); ``null`` while the voice is processing."""
    size_bytes: int


class VoiceQuality(BaseModel):
    snr_db: float | None = None
    clipping_ratio: float
    peak_dbfs: float
    rms_dbfs: float
    leading_silence_s: float
    trailing_silence_s: float
    warnings: list[str] = Field(default_factory=list)


class VoiceConsentOut(BaseModel):
    given_at: datetime
    text_version: str
    revoked_at: datetime | None


class VoiceOut(ApiModel):
    id: uuid.UUID
    name: str
    status: VoiceStatusLiteral
    error: ResourceError | None
    language: LanguageCode | None
    detected_language: LanguageCode | None
    engine_id: str | None
    transcript: str | None
    transcript_source: Literal["auto", "user"] | None
    reference: VoiceReference | None
    quality: VoiceQuality | None
    consent: VoiceConsentOut
    preview_generation_id: uuid.UUID | None
    job_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class VoicePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=60)
    transcript: str | None = Field(default=None, max_length=2000)
    language: LanguageCode | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = " ".join(value.split())
        if not value:
            raise ValueError("name must not be blank")
        return value


class VoicePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, max_length=300)


class ConsentGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent_confirmed: bool
    consent_text_version: str = Field(min_length=1, max_length=32)


class VoiceCreateFields(BaseModel):
    """Validated non-file fields of the multipart ``POST /voices`` request."""

    name: str = Field(min_length=1, max_length=60)
    language_hint: LanguageOrAuto = "auto"
    consent_confirmed: bool
    consent_text_version: str = Field(min_length=1, max_length=32)
    transcript: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("transcript")
    @classmethod
    def _strip_transcript(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = " ".join(value.split())
        return value or None
