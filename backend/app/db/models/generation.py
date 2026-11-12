"""Generation and generation file models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.user import User
    from app.db.models.voice import VoiceProfile


class GenerationKind(StrEnum):
    GENERATION = "generation"
    PREVIEW = "preview"
    CONVERSATION_TURN = "conversation_turn"


class GenerationStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


GenerationStatus.ALL = (
    GenerationStatus.QUEUED,
    GenerationStatus.PROCESSING,
    GenerationStatus.COMPLETED,
    GenerationStatus.FAILED,
    GenerationStatus.CANCELLED,
)
GenerationStatus.TERMINAL = (
    GenerationStatus.COMPLETED,
    GenerationStatus.FAILED,
    GenerationStatus.CANCELLED,
)


class Generation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "generations"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    voice_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("voice_profiles.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    voice_name: Mapped[str] = mapped_column(String(60), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    text_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_language: Mapped[str] = mapped_column(String(8), nullable=False)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    requested_engine_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    engine_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    speed: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    quality: Mapped[str] = mapped_column(String(16), nullable=False)
    output_format: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), index=True, nullable=False, default=GenerationStatus.QUEUED
    )
    progress: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delete_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )

    owner: Mapped[User] = relationship("User", back_populates="generations")
    voice: Mapped[VoiceProfile | None] = relationship(
        "VoiceProfile", back_populates="generations"
    )
    file: Mapped[GenerationFile | None] = relationship(
        "GenerationFile",
        back_populates="generation",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_generations_owner_id_created_at", "owner_id", "created_at"),
        Index("ix_generations_delete_after", "delete_after"),
    )


class GenerationFile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "generation_files"

    generation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("generations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    channels: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    generation: Mapped[Generation] = relationship(
        "Generation", back_populates="file"
    )
