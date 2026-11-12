"""Voice profile, consent and reference file models."""

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
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.generation import Generation
    from app.db.models.user import User


class ReferenceRole(StrEnum):
    ORIGINAL = "original"
    PROCESSED = "processed"


class VoiceStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    CONSENT_REVOKED = "consent_revoked"


VoiceStatus.ALL = (
    VoiceStatus.PROCESSING,
    VoiceStatus.READY,
    VoiceStatus.FAILED,
    VoiceStatus.CONSENT_REVOKED,
)
VoiceStatus.TERMINAL = (
    VoiceStatus.READY,
    VoiceStatus.FAILED,
    VoiceStatus.CONSENT_REVOKED,
)


class VoiceProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "voice_profiles"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False, default=VoiceStatus.PROCESSING
    )
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    language_hint: Mapped[str | None] = mapped_column(String(8), nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    detected_language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    engine_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_source: Mapped[str | None] = mapped_column(String(8), nullable=True)
    user_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    fingerprint: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    warnings: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    preview_generation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delete_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )

    owner: Mapped[User] = relationship("User", back_populates="voices")
    consents: Mapped[list[VoiceConsent]] = relationship(
        "VoiceConsent",
        back_populates="voice",
        cascade="all, delete-orphan",
        order_by="VoiceConsent.given_at.desc()",
    )
    reference_files: Mapped[list[VoiceReferenceFile]] = relationship(
        "VoiceReferenceFile",
        back_populates="voice",
        cascade="all, delete-orphan",
    )
    generations: Mapped[list[Generation]] = relationship(
        "Generation", back_populates="voice"
    )

    __table_args__ = (
        Index("ix_voice_profiles_owner_id_created_at", "owner_id", "created_at"),
    )

    def reference_file(self, role: ReferenceRole | str) -> VoiceReferenceFile | None:
        role_str = role.value if isinstance(role, ReferenceRole) else role
        for rf in self.reference_files:
            if rf.role == role_str:
                return rf
        return None

    @property
    def latest_consent(self) -> VoiceConsent | None:
        if not self.consents:
            return None
        return max(self.consents, key=lambda c: c.given_at)

    @property
    def has_active_consent(self) -> bool:
        return any(c.revoked_at is None for c in self.consents)

    @property
    def is_ready(self) -> bool:
        return self.status == VoiceStatus.READY


class VoiceConsent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "voice_consents"

    voice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("voice_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    consent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    text_version: Mapped[str] = mapped_column(String(32), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    given_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    voice: Mapped[VoiceProfile] = relationship("VoiceProfile", back_populates="consents")


class VoiceReferenceFile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "voice_reference_files"

    voice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("voice_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    codec: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    channels: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    speech_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    voice: Mapped[VoiceProfile] = relationship(
        "VoiceProfile", back_populates="reference_files"
    )

    __table_args__ = (
        UniqueConstraint("voice_id", "role", name="uq_voice_reference_files_voice_id_role"),
    )
