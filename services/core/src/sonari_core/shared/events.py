"""Events on Redis Streams: the message shape, stream names and the publisher.

Contexts never publish directly. They write an `EventMessage` to their outbox in the same
transaction as the state change (`shared.outbox`), and the relay publishes it (ADR-0007).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from redis.asyncio import Redis

STREAM_PREFIX = "events"
DEAD_LETTER_PREFIX = "dead"


def stream_name(event_type: str) -> str:
    """One stream per event type, named after the contract: `events.UserRegistered`."""
    return f"{STREAM_PREFIX}.{event_type}"


def dead_letter_stream(event_type: str) -> str:
    """Where a consumer parks entries it gave up on: `dead.events.UserRegistered`."""
    return f"{DEAD_LETTER_PREFIX}.{stream_name(event_type)}"


@dataclass(frozen=True)
class EventMessage:
    """One event. `event_id` is the contract's `eventId`; consumers deduplicate on it."""

    event_id: str
    event_type: str
    payload: Mapping[str, Any]


class EventPublisher(Protocol):
    async def publish(self, message: EventMessage) -> None: ...


class RedisStreamPublisher:
    """Appends to the event type's stream. A retried publish appends a second entry with
    the same `event_id`; consumers are idempotent for exactly that reason."""

    def __init__(self, redis: Redis, max_length: int = 100_000) -> None:
        self._redis = redis
        self._max_length = max_length

    async def publish(self, message: EventMessage) -> None:
        await self._redis.xadd(
            stream_name(message.event_type),
            {"event_id": message.event_id, "data": json.dumps(dict(message.payload))},
            maxlen=self._max_length,
            approximate=True,
        )
