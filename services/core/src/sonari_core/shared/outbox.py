"""The transactional outbox (ADR-0007).

A context writes its state change and an outbox document in one MongoDB transaction. The
relay later publishes unsent documents to Redis Streams and marks them sent. A crash after
the publish and before the mark makes the relay publish again: delivery is at least once,
and consumers deduplicate on `event_id` (`shared.consumer`).

Each context has its own `outbox` collection in its own database (ADR-0001).
"""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol, TypeVar

from opentelemetry import trace
from opentelemetry.trace import SpanKind
from pymongo import ASCENDING, IndexModel
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase

from sonari_core.shared.contexts import ContextSpec, MongoClient
from sonari_core.shared.events import EventMessage, EventPublisher, stream_name

OUTBOX_COLLECTION = "outbox"
# Sent entries are kept a week for debugging, then MongoDB deletes them.
SENT_RETENTION_S = 7 * 24 * 3600

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

T = TypeVar("T")
Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def run_in_transaction(
    client: MongoClient, work: Callable[[AsyncClientSession], Awaitable[T]]
) -> T:
    """Run `work` in one transaction, retried on transient errors. `work` may run twice,
    so it must not have effects outside the session."""
    async with client.start_session() as session:
        return await session.with_transaction(work)


class Outbox(Protocol):
    """What the relay needs from an outbox."""

    async def unsent(self, limit: int) -> Sequence[EventMessage]: ...

    async def mark_sent(self, event_ids: Sequence[str], now: datetime) -> None: ...


class MongoOutbox:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database[OUTBOX_COLLECTION]

    async def ensure_indexes(self) -> None:
        await self._collection.create_indexes(
            [
                # The relay's query: unsent entries, oldest first.
                IndexModel([("sent_at", ASCENDING), ("created_at", ASCENDING)]),
                # Only sent entries carry a date in `sent_at`, so only they expire.
                IndexModel([("sent_at", ASCENDING)], expireAfterSeconds=SENT_RETENTION_S),
            ]
        )

    async def add(self, message: EventMessage, now: datetime, session: AsyncClientSession) -> None:
        """Write inside the caller's transaction, never outside one: an outbox entry
        written on its own could commit while the state change it announces does not."""
        if not session.in_transaction:
            raise RuntimeError("outbox entries must be written inside a transaction")
        await self._collection.insert_one(
            {
                "_id": message.event_id,
                "type": message.event_type,
                "payload": dict(message.payload),
                "created_at": now,
                "sent_at": None,
            },
            session=session,
        )

    async def unsent(self, limit: int) -> list[EventMessage]:
        cursor = self._collection.find({"sent_at": None}).sort("created_at", ASCENDING)
        return [
            EventMessage(event_id=doc["_id"], event_type=doc["type"], payload=doc["payload"])
            async for doc in cursor.limit(limit)
        ]

    async def mark_sent(self, event_ids: Sequence[str], now: datetime) -> None:
        await self._collection.update_many(
            {"_id": {"$in": list(event_ids)}, "sent_at": None}, {"$set": {"sent_at": now}}
        )


class OutboxRelay:
    """Moves one context's outbox entries to Redis Streams, oldest first."""

    def __init__(
        self,
        outbox: Outbox,
        publisher: EventPublisher,
        *,
        batch_size: int = 100,
        clock: Clock = _utc_now,
    ) -> None:
        self._outbox = outbox
        self._publisher = publisher
        self._batch_size = batch_size
        self._clock = clock

    async def run_once(self) -> int:
        """Publish one batch, then mark it sent. Returns how many entries were published.

        Entries are marked after the whole batch is published: a crash in between
        republishes the batch, which consumers absorb. A failed publish stops the batch
        so later entries never overtake it; the published prefix is still marked.
        """
        published: list[str] = []
        try:
            for message in await self._outbox.unsent(self._batch_size):
                with tracer.start_as_current_span(
                    f"send {stream_name(message.event_type)}",
                    kind=SpanKind.PRODUCER,
                    attributes={
                        "messaging.system": "redis",
                        "messaging.operation.type": "send",
                        "messaging.destination.name": stream_name(message.event_type),
                        "messaging.message.id": message.event_id,
                    },
                ):
                    await self._publisher.publish(message)
                published.append(message.event_id)
        finally:
            if published:
                await self._outbox.mark_sent(published, self._clock())
        return len(published)

    async def run(self, stop: asyncio.Event, interval_s: float) -> None:
        """Poll until `stop` is set. Errors are logged and retried on the next tick."""
        while not stop.is_set():
            try:
                while await self.run_once() == self._batch_size:
                    pass  # a full batch means more may be waiting
            except Exception:
                logger.exception("outbox relay failed; retrying")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=interval_s)


class OutboxRelays:
    """One relay task per context that has an outbox, for the life of the process.

    Every replica of the process runs them. Two relays may then publish the same entry,
    which costs a duplicate and nothing else: consumers deduplicate.
    """

    def __init__(
        self,
        client: MongoClient,
        specs: Sequence[ContextSpec],
        publisher: EventPublisher,
        interval_s: float,
    ) -> None:
        self._outboxes = [MongoOutbox(spec.database(client)) for spec in specs if spec.outbox]
        self._publisher = publisher
        self._interval_s = interval_s
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        for outbox in self._outboxes:
            await outbox.ensure_indexes()
            relay = OutboxRelay(outbox, self._publisher)
            self._tasks.append(asyncio.create_task(relay.run(self._stop, self._interval_s)))

    async def stop(self) -> None:
        self._stop.set()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
