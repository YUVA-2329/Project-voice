"""Aggregates every v1 router under ``/api/v1``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    api_keys,
    audit,
    auth,
    conversation,
    generations,
    jobs,
    media,
    system,
    users,
    voices,
)

api_router = APIRouter()
for module in (
    auth,
    users,
    voices,
    generations,
    jobs,
    system,
    api_keys,
    audit,
    media,
    conversation,
):
    api_router.include_router(module.router)
