"""The outbox and the event bus on the real MongoDB and Redis (`make infra`).

What the fakes in tests/test_event_bus.py cannot prove: that the user and its outbox
entry commit or roll back together, and that the crash and poison cases hold on a real
Redis consumer group. CI has no MongoDB or Redis and skips the file.
"""

from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis

from event_fakes import RecordingConsumer, SimulatedCrash
from sonari_core.app import CONTEXTS
from sonari_core.identity.models import User
from sonari_core.identity.ports import EmailTaken, UserRecord
from sonari_core.identity.stores import MongoUserStore
from sonari_core.shared.consumer import ConsumerConfig
from sonari_core.shared.contexts import init_contexts
from sonari_core.shared.events import (
    EventMessage,
    RedisStreamPublisher,
    dead_letter_stream,
    stream_name,
)
from sonari_core.shared.outbox import SENT_RETENTION_S, MongoOutbox, OutboxRelay
from sonari_core.shared.settings import Settings

FAST = ConsumerConfig(max_deliveries=3, retry_after_ms=0)
Database = AsyncDatabase[dict[str, Any]]


class CrashOnceOutbox(MongoOutbox):
    """The real outbox, limited to one run's event type (other unsent rows in the dev
    database are not this test's to send), whose first mark_sent dies like a killed
    process."""

    def __init__(self, database: Database, event_type: str) -> None:
        super().__init__(database)
        self._event_type = event_type
        self.crashed = False

    async def unsent(self, limit: int) -> list[EventMessage]:
        everything = await super().unsent(10_000)
        return [m for m in everything if m.event_type == self._event_type][:limit]

    async def mark_sent(self, event_ids: Sequence[str], now: datetime) -> None:
        if not self.crashed:
            self.crashed = True
            raise SimulatedCrash("relay died after publishing, before marking sent")
        await super().mark_sent(event_ids, now)


@pytest_asyncio.fixture
async def identity_db(live_settings: Settings, run_id: str) -> AsyncIterator[Database]:
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
        live_settings.mongo_uri, tz_aware=True
    )
    await init_contexts(client, CONTEXTS)
    database = client["identity"]
    await MongoOutbox(database).ensure_indexes()
    yield database
    await User.find({"email": {"$regex": f"^{run_id}"}}).delete()
    await database["outbox"].delete_many({"type": {"$regex": f"^It{run_id}"}})
    await client.close()


@pytest_asyncio.fixture
async def redis(live_settings: Settings, run_id: str) -> AsyncIterator[Redis]:
    client: Redis = Redis.from_url(live_settings.redis_url, decode_responses=True)
    yield client
    keys = [k async for k in client.scan_iter(f"consumed:{run_id}:*")]
    event_type = f"It{run_id}"
    await client.delete(stream_name(event_type), dead_letter_stream(event_type), *keys)
    await client.aclose()


def consumer_for(redis: Redis, run_id: str) -> RecordingConsumer:
    class Recorder(RecordingConsumer):
        event_type = f"It{run_id}"
        group = run_id

    return Recorder(redis, "worker-1", FAST)


def announcer(run_id: str) -> Any:
    def announce(user: UserRecord) -> EventMessage:
        event_id = str(uuid4())
        return EventMessage(event_id, f"It{run_id}", {"eventId": event_id, "userId": user.id})

    return announce


async def test_the_user_and_its_outbox_entry_commit_together(
    identity_db: Database, run_id: str
) -> None:
    user = await MongoUserStore().create(
        f"{run_id}@example.com", "hash", datetime.now(UTC), announcer(run_id)
    )

    entry = await identity_db["outbox"].find_one({"payload.userId": user.id})
    assert entry is not None
    assert entry["type"] == f"It{run_id}"
    assert entry["sent_at"] is None


async def test_a_taken_email_rolls_back_and_leaves_no_outbox_entry(
    identity_db: Database, run_id: str
) -> None:
    users, email = MongoUserStore(), f"{run_id}@example.com"
    await users.create(email, "hash", datetime.now(UTC), announcer(run_id))

    with pytest.raises(EmailTaken):
        await users.create(email, "hash", datetime.now(UTC), announcer(run_id))

    assert await identity_db["outbox"].count_documents({"type": f"It{run_id}"}) == 1


async def test_an_outbox_entry_cannot_be_written_outside_a_transaction(
    identity_db: Database, run_id: str
) -> None:
    message = EventMessage(str(uuid4()), f"It{run_id}", {})
    async with identity_db.client.start_session() as session:
        with pytest.raises(RuntimeError, match="inside a transaction"):
            await MongoOutbox(identity_db).add(message, datetime.now(UTC), session)


async def test_sent_entries_expire_and_unsent_ones_never_do(identity_db: Database) -> None:
    indexes = await identity_db["outbox"].index_information()

    ttl = [i for i in indexes.values() if "expireAfterSeconds" in i]
    assert [(i["key"], i["expireAfterSeconds"]) for i in ttl] == [
        ([("sent_at", 1)], SENT_RETENTION_S)
    ]


async def test_a_relay_crash_on_the_real_stack_still_has_one_effect(
    identity_db: Database, redis: Redis, run_id: str
) -> None:
    user = await MongoUserStore().create(
        f"{run_id}@example.com", "hash", datetime.now(UTC), announcer(run_id)
    )
    consumer = consumer_for(redis, run_id)
    await consumer.setup()
    publisher = RedisStreamPublisher(redis)
    outbox = CrashOnceOutbox(identity_db, f"It{run_id}")

    with pytest.raises(SimulatedCrash):
        await OutboxRelay(outbox, publisher).run_once()
    assert await OutboxRelay(outbox, publisher).run_once() == 1
    for _ in range(2):
        await consumer.run_once()

    assert await redis.xlen(stream_name(f"It{run_id}")) == 2
    (event_id,) = consumer.effects
    assert consumer.effects[event_id] == 1
    assert (await redis.xpending(stream_name(f"It{run_id}"), run_id))["pending"] == 0
    entry = await identity_db["outbox"].find_one({"type": f"It{run_id}"})
    assert entry is not None and entry["sent_at"] is not None
    assert entry["payload"]["userId"] == user.id


async def test_a_poison_message_on_the_real_stack_is_dead_lettered(
    redis: Redis, run_id: str
) -> None:
    consumer = consumer_for(redis, run_id)
    await consumer.setup()
    poison = EventMessage(str(uuid4()), f"It{run_id}", {"n": 0})
    good = EventMessage(str(uuid4()), f"It{run_id}", {"n": 1})
    consumer.poison.add(poison.event_id)
    for message in (poison, good):
        await RedisStreamPublisher(redis).publish(message)

    for _ in range(FAST.max_deliveries + 2):
        await consumer.run_once()

    assert consumer.attempts[poison.event_id] == FAST.max_deliveries
    assert consumer.effects == {good.event_id: 1}
    assert (await redis.xpending(stream_name(f"It{run_id}"), run_id))["pending"] == 0
    ((_, dead),) = await redis.xrange(dead_letter_stream(f"It{run_id}"))
    assert dead["event_id"] == poison.event_id
