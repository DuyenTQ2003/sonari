"""The consumer base class: consumer groups, retries, a dead-letter stream, idempotency.

Delivery is at least once (the outbox relay may publish an event twice, and a failed
handler is retried), so the effect is made exactly once by remembering processed
`event_id`s per consumer group for `processed_ttl_s`. The id is recorded after the
handler returns, so a crash inside that gap applies the event again: a handler whose
effect is a database write should still make it an upsert.

An entry is acknowledged only after its handler succeeds. A failed entry stays pending
and is reclaimed after `retry_after_ms`. Once it has been delivered `max_deliveries`
times it moves to the dead-letter stream, so one poison message cannot hold the group.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar, cast

from opentelemetry import trace
from opentelemetry.trace import SpanKind
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from redis.typing import EncodableT, FieldT

from sonari_core.shared.events import dead_letter_stream, stream_name

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

Fields = dict[str, str]
Entries = list[tuple[str, Fields]]


@dataclass(frozen=True)
class ConsumerConfig:
    max_deliveries: int = 5
    retry_after_ms: int = 30_000  # how long a failed entry waits before it is redelivered
    processed_ttl_s: int = 7 * 24 * 3600  # longer than any redelivery can take
    batch_size: int = 50
    block_ms: int = 1000


class EventConsumer(ABC):
    """Subclasses set `event_type` and `group` and implement `handle`.

    `group` names the consuming purpose (`learning.profile`), not the process: every
    replica joins the same group under its own `consumer_name`. The Redis client must
    use `decode_responses=True`.
    """

    event_type: ClassVar[str]
    group: ClassVar[str]

    def __init__(self, redis: Redis, consumer_name: str, config: ConsumerConfig | None = None):
        self._redis = redis
        self._name = consumer_name
        self._config = config or ConsumerConfig()
        self._stream = stream_name(self.event_type)

    @abstractmethod
    async def handle(self, event_id: str, payload: dict[str, Any]) -> None:
        """Apply one event. Raising leaves the entry pending, to be retried."""

    async def setup(self) -> None:
        """Create the group, reading the stream from its start, unless it exists."""
        try:
            await self._redis.xgroup_create(self._stream, self.group, id="0", mkstream=True)
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def run_once(self, block_ms: int | None = None) -> int:
        """Retry due pending entries, then read new ones. Returns how many were seen."""
        seen = await self._retry_pending()
        response = cast(
            list[tuple[str, Entries]] | None,
            await self._redis.xreadgroup(
                self.group,
                self._name,
                {self._stream: ">"},
                count=self._config.batch_size,
                block=block_ms,
            ),
        )
        for _, entries in response or []:
            for entry_id, fields in entries:
                await self._process(entry_id, fields)
                seen += 1
        return seen

    async def run(self, stop: asyncio.Event) -> None:
        await self.setup()
        while not stop.is_set():
            try:
                await self.run_once(self._config.block_ms)
            except Exception:
                logger.exception("consumer loop failed; retrying", extra={"group": self.group})
                await asyncio.sleep(1)

    async def _retry_pending(self) -> int:
        _, claimed, deleted = cast(
            tuple[str, Entries, list[str]],
            await self._redis.xautoclaim(
                self._stream,
                self.group,
                self._name,
                min_idle_time=self._config.retry_after_ms,
                start_id="0-0",
                count=self._config.batch_size,
            ),
        )
        if deleted:  # trimmed from the stream while pending: nothing left to process
            await self._redis.xack(self._stream, self.group, *deleted)
        for entry_id, fields in claimed:
            deliveries = await self._deliveries(entry_id)
            if deliveries > self._config.max_deliveries:
                await self._dead_letter(entry_id, fields, deliveries)
            else:
                await self._process(entry_id, fields)
        return len(claimed)

    async def _deliveries(self, entry_id: str) -> int:
        """How often the entry has been delivered, counting the claim just made."""
        (info,) = await self._redis.xpending_range(
            self._stream, self.group, min=entry_id, max=entry_id, count=1
        )
        return int(info["times_delivered"])

    async def _dead_letter(self, entry_id: str, fields: Fields, deliveries: int) -> None:
        logger.error(
            "event dead-lettered after max deliveries",
            extra={"group": self.group, "entry_id": entry_id, "deliveries": deliveries},
        )
        dead: dict[FieldT, EncodableT] = dict(fields.items())
        dead.update(source_entry_id=entry_id, group=self.group, deliveries=str(deliveries))
        async with self._redis.pipeline(transaction=True) as pipe:  # both or neither
            pipe.xadd(dead_letter_stream(self.event_type), dead)
            pipe.xack(self._stream, self.group, entry_id)
            await pipe.execute()

    async def _process(self, entry_id: str, fields: Fields) -> None:
        with tracer.start_as_current_span(
            f"process {self._stream}",
            kind=SpanKind.CONSUMER,
            attributes={
                "messaging.system": "redis",
                "messaging.operation.type": "process",
                "messaging.destination.name": self._stream,
                "messaging.consumer.group.name": self.group,
                "messaging.message.id": fields.get("event_id", ""),
            },
        ):
            try:
                event_id = fields["event_id"]
                payload = json.loads(fields["data"])
                if await self._redis.exists(self._processed_key(event_id)):
                    await self._redis.xack(self._stream, self.group, entry_id)
                    return  # a redelivery of an event already applied
                await self.handle(event_id, payload)
            except Exception:
                logger.exception(
                    "event handler failed; will retry",
                    extra={"group": self.group, "entry_id": entry_id},
                )
                return
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.set(self._processed_key(event_id), entry_id, ex=self._config.processed_ttl_s)
                pipe.xack(self._stream, self.group, entry_id)
                await pipe.execute()

    def _processed_key(self, event_id: str) -> str:
        return f"consumed:{self.group}:{event_id}"
