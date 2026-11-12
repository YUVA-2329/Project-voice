"""Generation schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import (
    ApiModel,
    LanguageCode,
    LanguageOrAuto,
    OutputFormat,
    Progress,
    Quality,
    ResourceError,
)

GenerationStatusLiteral = Literal["queued", "processing", "completed", "failed", "cancelled"]


class GenerationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice_id: uuid.UUID
    text: str = Field(min_length=1, max_length=20000)
    """Upper bound here is generous; the real cap (``PV_MAX_TEXT_CHARS``) applies after
    normalisation in the service layer so the error is ``validation_error`` with a clear field."""
    language: LanguageOrAuto | None = None
    engine_id: str | None = Field(default=None, max_length=64)
    speed: float | None = Field(default=None, ge=0.5, le=2.0)
    output_format: OutputFormat | None = None
    quality: Quality | None = None


class GenerationOutput(BaseModel):
    format: str
    duration_seconds: float
    sample_rate: int
    size_bytes: int


class GenerationMetrics(BaseModel):
    inference_seconds: float
    total_seconds: float
    real_time_factor: float
    chunks: int
    device: Literal["cpu", "cuda"]
    peak_dbfs: float
    clipping_ratio: float


class GenerationOut(ApiModel):
    id: uuid.UUID
    voice_id: uuid.UUID | None
    voice_name: str
    text: str
    language: LanguageCode | None
    requested_language: LanguageOrAuto
    engine_id: str | None
    status: GenerationStatusLiteral
    progress: Progress | None
    error: ResourceError | None
    output: GenerationOutput | None
    metrics: GenerationMetrics | None
    job_id: uuid.UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class MediaUrlOut(BaseModel):
    url: str
    expires_at: datetime
