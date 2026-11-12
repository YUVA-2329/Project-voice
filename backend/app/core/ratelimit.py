"""Redis sliding-window rate limiter.

One sorted set per ``(bucket, identity)``; members are request timestamps.  A request is allowed
when fewer than ``limit`` members fall inside the last ``window`` seconds.  The check is atomic
(Lua) so concurrent requests cannot overshoot.  If Redis is unreachable the limiter *fails open*
and logs a warning — availability of the product wins over strictness of the limiter.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)

# KEYS[1] = zset key; ARGV[1] = now (float seconds); ARGV[2] = window; ARGV[3] = limit;
# ARGV[4] = unique member suffix.  Returns {allowed, count, oldest_ts}.
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count < limit then
  redis.call('ZADD', key, now, tostring(now) .. '-' .. ARGV[4])
  redis.call('EXPIRE', key, math.ceil(window) + 1)
  return {1, count + 1, 0}
end
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
local oldest_ts = now
if oldest[2] then oldest_ts = tonumber(oldest[2]) end
return {0, count, oldest_ts}
"""


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int
    """Seconds until the oldest request leaves the window (0 when allowed)."""


class RateLimiter:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings
        self._script = redis.register_script(_SLIDING_WINDOW_LUA)
        self._counter = 0

    def limit_for(self, bucket: str) -> int:
        s = self._settings
        return {
            "auth": s.RATE_LIMIT_AUTH_PER_WINDOW,
            "upload": s.RATE_LIMIT_UPLOAD_PER_WINDOW,
            "generate": s.RATE_LIMIT_GENERATE_PER_WINDOW,
        }.get(bucket, s.RATE_LIMIT_DEFAULT_PER_WINDOW)

    async def check(
        self, bucket: str, identity: str, *, limit: int | None = None
    ) -> RateLimitDecision:
        limit = limit if limit is not None else self.limit_for(bucket)
        window = float(self._settings.RATE_LIMIT_WINDOW_SECONDS)
        if not self._settings.RATE_LIMIT_ENABLED:
            return RateLimitDecision(True, limit, limit, 0)
        key = f"pv:ratelimit:{bucket}:{identity}"
        now = time.time()
        self._counter = (self._counter + 1) % 1_000_000
        try:
            allowed, count, oldest = await self._script(
                keys=[key], args=[now, window, limit, self._counter]
            )
        except (RedisError, OSError) as exc:
            log.warning("ratelimit_redis_unavailable", bucket=bucket, error=str(exc))
            return RateLimitDecision(True, limit, limit, 0)
        if int(allowed) == 1:
            return RateLimitDecision(True, limit, max(0, limit - int(count)), 0)
        retry_after = int(max(1.0, float(oldest) + window - now + 0.999))
        return RateLimitDecision(False, limit, 0, retry_after)
