"""Job schema."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from app.schemas.common import ApiModel, Progress, ResourceError

JobKindLiteral = Literal["voice_create", "generation", "preview", "conversation_turn", "cleanup"]
JobStatusLiteral = Literal["queued", "running", "completed", "failed", "cancelled"]


class JobOut(ApiModel):
    id: uuid.UUID
    kind: JobKindLiteral
    status: JobStatusLiteral
    progress: Progress | None
    error: ResourceError | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    resource_type: str | None
    resource_id: uuid.UUID | None
