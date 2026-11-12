"""Audit schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import ApiModel


class AuditEventOut(ApiModel):
    id: uuid.UUID
    action: str
    resource_type: str | None
    resource_id: uuid.UUID | None
    ip: str | None
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
