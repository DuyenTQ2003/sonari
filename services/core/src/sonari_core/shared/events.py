"""Publishing events to Redis Streams.

P14 publishes directly after the state change commits. That can lose an event if the
process dies in between; the outbox (P15) replaces this call path.
"""

import json
from collections.abc import Mapping
from typing import Any, Protocol

from redis.asyncio import Redis

STREAM_PREFIX = "events"


def stream_name(event_type: str) -> str:
    """One stream per event type, named after the contract: `events.UserRegistered`."""
    return f"{STREAM_PREFIX}.{event_type}"


class EventPublisher(Protocol):
    async def publish(self, event_type: str, payload: Mapping[str, Any]) -> None: ...


class RedisStreamPublisher:
    def __init__(self, redis: Redis, max_length: int = 100_000) -> None:
        self._redis = redis
        self._max_length = max_length

    async def publish(self, event_type: str, payload: Mapping[str, Any]) -> None:
        await self._redis.xadd(
            stream_name(event_type),
            {"data": json.dumps(payload)},
            maxlen=self._max_length,
            approximate=True,
        )
