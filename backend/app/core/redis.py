"""Process-wide asyncio Redis client for the API process.

The worker uses the synchronous client from ``app.jobs.queues``; this module is only for the
API (rate limiting, heartbeat lookups, queue depth, language-matrix cache).
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import get_settings

_client: aioredis.Redis | None = None


def get_async_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = aioredis.from_url(
            settings.REDIS_URL,
            protocol=2,
            decode_responses=False,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
            health_check_interval=30,
        )
    return _client


async def close_async_redis() -> None:
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        finally:
            _client = None


def reset_async_redis() -> None:
    """Drop the cached client without awaiting (for use outside the client's event loop)."""
    global _client
    _client = None
