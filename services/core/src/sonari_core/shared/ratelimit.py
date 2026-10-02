"""A sliding-window rate limiter on Redis.

Each allowed hit is one member of a sorted set scored by its time. A hit that would
exceed the limit is removed again: refused attempts do not count, so someone hammering a
key cannot keep a victim locked out for longer than one window.
"""

import math
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    retry_after_s: int = 0


class RateLimiter(Protocol):
    async def hit(self, key: str, limit: int, window_s: int) -> RateDecision: ...


class RedisSlidingWindowLimiter:
    def __init__(self, redis: Redis, clock: Callable[[], float] = time.time) -> None:
        self._redis = redis
        self._clock = clock

    async def hit(self, key: str, limit: int, window_s: int) -> RateDecision:
        redis_key = f"ratelimit:{key}"
        now_ms = int(self._clock() * 1000)
        window_ms = window_s * 1000
        member = f"{now_ms}-{uuid.uuid4().hex[:8]}"  # unique even for two hits in one ms

        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(redis_key, 0, now_ms - window_ms)
            pipe.zadd(redis_key, {member: now_ms})
            pipe.zcard(redis_key)
            pipe.zrange(redis_key, 0, 0, withscores=True)
            pipe.pexpire(redis_key, window_ms)
            _, _, count, oldest, _ = await pipe.execute()

        if count <= limit:
            return RateDecision(allowed=True)

        await self._redis.zrem(redis_key, member)
        oldest_ms = int(oldest[0][1])
        retry_after = math.ceil((oldest_ms + window_ms - now_ms) / 1000)
        return RateDecision(allowed=False, retry_after_s=max(retry_after, 1))
