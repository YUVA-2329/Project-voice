"""Conversation-mode schemas (REST part; the WebSocket protocol is in ``api/v1/conversation``)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ConversationEngineOut(BaseModel):
    id: Literal["mirror", "llm"]
    available: bool
    reason: str | None = None
