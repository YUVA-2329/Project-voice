"""Processing job models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class JobKind(StrEnum):
    VOICE_CREATE = "voice_create"
    GENERATION = "generation"
    PREVIEW = "preview"
    CONVERSATION_TURN = "conversation_turn"
    CLEANUP = "cleanup"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


JobStatus.ALL = (
    JobStatus.QUEUED,
    JobStatus.RUNNING,
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
)
JobStatus.TERMINAL = (
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
)


class ProcessingJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "processing_jobs"

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=JobStatus.QUEUED
    )
    queue: Mapped[str] = mapped_column(String(32), nullable=False)
    rq_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    progress: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worker_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    owner: Mapped[User | None] = relationship("User")

    __table_args__ = (
        Index("ix_processing_jobs_resource", "resource_type", "resource_id"),
        Index("ix_processing_jobs_status_created_at", "status", "created_at"),
    )
