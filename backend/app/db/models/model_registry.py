"""Model registry model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ModelRegistryEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "model_registry"

    engine_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    licence: Mapped[str] = mapped_column(String(128), nullable=False)
    weight_licence: Mapped[str] = mapped_column(String(128), nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    unavailable_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    loaded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    device: Mapped[str | None] = mapped_column(String(8), nullable=True)
    tts_languages: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    cloning_languages: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    cross_lingual: Mapped[bool] = mapped_column(Boolean, nullable=False)
    requires_reference_text: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    resource: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    worker_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
