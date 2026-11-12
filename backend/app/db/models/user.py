"""User and session models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.api_key import ApiKey
    from app.db.models.generation import Generation
    from app.db.models.voice import VoiceProfile


def default_preferences() -> dict[str, Any]:
    return {
        "default_language": "auto",
        "default_engine": None,
        "output_format": "wav",
        "speed": 1.0,
        "theme": "system",
        "mode": "simple",
    }


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=default_preferences
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sessions: Mapped[list[UserSession]] = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list[ApiKey]] = relationship(
        "ApiKey", back_populates="user", cascade="all, delete-orphan"
    )
    voices: Mapped[list[VoiceProfile]] = relationship(
        "VoiceProfile", back_populates="owner", cascade="all, delete-orphan"
    )
    generations: Mapped[list[Generation]] = relationship(
        "Generation", back_populates="owner", cascade="all, delete-orphan"
    )


class UserSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    refresh_token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rotated_from_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("ix_user_sessions_user_id_expires_at", "user_id", "expires_at"),
    )
