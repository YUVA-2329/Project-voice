"""Shared schema primitives."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

LanguageCode = Literal["en", "te", "hi", "kn", "ta", "ml", "zh"]
LanguageOrAuto = Literal["auto", "en", "te", "hi", "kn", "ta", "ml", "zh"]
OutputFormat = Literal["wav", "mp3", "flac"]
Quality = Literal["fast", "balanced", "high"]

LANGUAGE_CODES: tuple[str, ...] = ("en", "te", "hi", "kn", "ta", "ml", "zh")

T = TypeVar("T")


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class ResourceError(BaseModel):
    code: str
    message: str


class Progress(BaseModel):
    stage: str
    current: int
    total: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class PaginationParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
