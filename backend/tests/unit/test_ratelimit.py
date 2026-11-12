"""Sliding-window rate limiter against the local Redis (fails open when Redis is unreachable)."""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.ratelimit import RateLimiter


async def test_sliding_window_limits_and_retry_after() -> None:
    settings = get_settings().model_copy(update={"RATE_LIMIT_WINDOW_SECONDS": 60})
    client = aioredis.from_url(settings.REDIS_URL)
    try:
        limiter = RateLimiter(client, settings)
        decisions = [await limiter.check("auth", "ip:1.2.3.4", limit=3) for _ in range(4)]
        assert [d.allowed for d in decisions] == [True, True, True, False]
        assert decisions[0].remaining == 2 and decisions[2].remaining == 0
        assert 1 <= decisions[3].retry_after <= 61
        # Another identity has its own bucket.
        assert (await limiter.check("auth", "ip:9.9.9.9", limit=3)).allowed
    finally:
        await client.aclose()


async def test_disabled_limiter_always_allows() -> None:
    settings = get_settings().model_copy(update={"RATE_LIMIT_ENABLED": False})
    client = aioredis.from_url(settings.REDIS_URL)
    try:
        limiter = RateLimiter(client, settings)
        for _ in range(5):
            assert (await limiter.check("auth", "ip:x", limit=1)).allowed
    finally:
        await client.aclose()


async def test_fails_open_when_redis_is_down() -> None:
    settings = get_settings()
    client = aioredis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    try:
        limiter = RateLimiter(client, settings)
        decision = await limiter.check("auth", "ip:down", limit=1)
        assert decision.allowed
        assert decision.retry_after == 0
    finally:
        await client.aclose()
