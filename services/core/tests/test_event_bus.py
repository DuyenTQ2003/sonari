"""The event bus on an in-process Redis (fakeredis): relay, consumer group, dead letters.

tests/integration/test_events_live.py runs the crash and poison cases on the real
MongoDB and Redis.
"""

import json
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from redis.asyncio import Redis

from event_fakes import InMemoryOutbox, RecordingConsumer, SimulatedCrash, message
from sonari_core.shared.consumer import ConsumerConfig
from sonari_core.shared.events import (
    EventMessage,
    RedisStreamPublisher,
    dead_letter_stream,
    stream_name,
)
from sonari_core.shared.outbox import OutboxRelay

# Failed entries are due for redelivery at once, so each run_once is one retry round.
FAST = ConsumerConfig(max_deliveries=3, retry_after_ms=0)
STREAM = stream_name(RecordingConsumer.event_type)
GROUP = RecordingConsumer.group


@pytest_asyncio.fixture
async def redis() -> AsyncIterator[Redis]:
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def consumer(redis: Redis) -> RecordingConsumer:
    recorder = RecordingConsumer(redis, "worker-1", FAST)
    await recorder.setup()
    return recorder


def relay_for(outbox: InMemoryOutbox, redis: Redis) -> OutboxRelay:
    return OutboxRelay(outbox, RedisStreamPublisher(redis))


async def pending(redis: Redis) -> int:
    summary = await redis.xpending(STREAM, GROUP)
    return int(summary["pending"])


# --- the two failure modes the outbox and the consumer exist for -------------------------


async def test_a_relay_crash_between_publish_and_mark_sent_has_one_effect(
    redis: Redis, consumer: RecordingConsumer
) -> None:
    outbox = InMemoryOutbox()
    event = message()
    outbox.add(event)

    outbox.crash_on_mark_sent = True
    with pytest.raises(SimulatedCrash):
        await relay_for(outbox, redis).run_once()
    assert await outbox.unsent(10) == [event]  # never marked, so the restarted relay resends
    assert await relay_for(outbox, redis).run_once() == 1

    assert await redis.xlen(STREAM) == 2  # delivered twice ...
    await consumer.run_once()
    await consumer.run_once()

    assert consumer.effects == {event.event_id: 1}  # ... applied once
    assert await pending(redis) == 0  # and both entries acknowledged
    assert await outbox.unsent(10) == []


async def test_a_poison_message_is_dead_lettered_and_does_not_block_the_group(
    redis: Redis, consumer: RecordingConsumer
) -> None:
    publisher = RedisStreamPublisher(redis)
    poison, good = message(), message()
    consumer.poison.add(poison.event_id)
    await publisher.publish(poison)
    await publisher.publish(good)

    for _ in range(FAST.max_deliveries + 1):
        await consumer.run_once()

    assert consumer.attempts[poison.event_id] == FAST.max_deliveries
    assert consumer.effects == {good.event_id: 1}
    assert await pending(redis) == 0
    ((_, dead),) = await redis.xrange(dead_letter_stream(RecordingConsumer.event_type))
    assert dead["event_id"] == poison.event_id
    assert dead["group"] == GROUP
    assert dead["deliveries"] == str(FAST.max_deliveries + 1)
    assert json.loads(dead["data"]) == dict(poison.payload)

    # Nothing is retried after that: the group is free.
    await consumer.run_once()
    assert consumer.attempts[poison.event_id] == FAST.max_deliveries


# --- the rest of the contract ------------------------------------------------------------


async def test_an_entry_is_acknowledged_only_after_its_handler_succeeds(
    redis: Redis, consumer: RecordingConsumer
) -> None:
    event = message()
    consumer.fail_times[event.event_id] = 2
    await RedisStreamPublisher(redis).publish(event)

    await consumer.run_once()
    assert await pending(redis) == 1
    await consumer.run_once()
    assert await pending(redis) == 1
    await consumer.run_once()

    assert await pending(redis) == 0
    assert consumer.effects == {event.event_id: 1}
    assert await redis.xlen(dead_letter_stream(RecordingConsumer.event_type)) == 0


async def test_a_failed_entry_waits_retry_after_ms_before_it_is_redelivered(
    redis: Redis,
) -> None:
    patient = RecordingConsumer(redis, "worker-1", ConsumerConfig(retry_after_ms=60_000))
    await patient.setup()
    event = message()
    patient.fail_times[event.event_id] = 1
    await RedisStreamPublisher(redis).publish(event)

    await patient.run_once()
    await patient.run_once()

    assert patient.attempts[event.event_id] == 1
    assert await pending(redis) == 1


async def test_a_malformed_entry_is_dead_lettered_too(
    redis: Redis, consumer: RecordingConsumer
) -> None:
    await redis.xadd(STREAM, {"data": "{not json"})

    for _ in range(FAST.max_deliveries + 1):
        await consumer.run_once()

    assert consumer.attempts == {}
    assert await pending(redis) == 0
    assert await redis.xlen(dead_letter_stream(RecordingConsumer.event_type)) == 1


async def test_two_groups_each_get_every_event(redis: Redis, consumer: RecordingConsumer) -> None:
    class OtherGroup(RecordingConsumer):
        group = "test.other"

    other = OtherGroup(redis, "worker-1", FAST)
    await other.setup()
    event = message()
    await RedisStreamPublisher(redis).publish(event)

    await consumer.run_once()
    await other.run_once()

    assert consumer.effects == other.effects == {event.event_id: 1}


async def test_setup_twice_keeps_the_group_and_its_position(
    redis: Redis, consumer: RecordingConsumer
) -> None:
    await RedisStreamPublisher(redis).publish(message())
    await consumer.run_once()

    await consumer.setup()

    assert await consumer.run_once() == 0


async def test_the_relay_publishes_oldest_first_and_marks_what_it_sent(redis: Redis) -> None:
    outbox = InMemoryOutbox()
    events = [message(n=n) for n in range(3)]
    for event in events:
        outbox.add(event)

    assert await relay_for(outbox, redis).run_once() == 3
    assert await relay_for(outbox, redis).run_once() == 0

    entries = await redis.xrange(STREAM)
    assert [fields["event_id"] for _, fields in entries] == [e.event_id for e in events]
    assert [json.loads(fields["data"])["n"] for _, fields in entries] == [0, 1, 2]
    assert set(outbox.sent) == {e.event_id for e in events}


async def test_a_failed_publish_keeps_the_entry_and_everything_after_it(redis: Redis) -> None:
    class FlakyPublisher(RedisStreamPublisher):
        failures = 1

        async def publish(self, event: EventMessage) -> None:
            if event.payload["n"] == 1 and self.failures:
                self.failures -= 1
                raise ConnectionError("redis is down")
            await super().publish(event)

    outbox = InMemoryOutbox()
    events = [message(n=n) for n in range(3)]
    for event in events:
        outbox.add(event)
    relay = OutboxRelay(outbox, FlakyPublisher(redis))

    with pytest.raises(ConnectionError):
        await relay.run_once()
    assert set(outbox.sent) == {events[0].event_id}

    assert await relay.run_once() == 2
    entries = await redis.xrange(STREAM)
    assert [json.loads(fields["data"])["n"] for _, fields in entries] == [0, 1, 2]
