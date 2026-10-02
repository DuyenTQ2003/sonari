import asyncio

import pytest

from sonari_speech.errors import MessageKey
from sonari_speech.runtime.gate import InferenceGate, Overloaded


class Probe:
    """Counts how many bodies run at once and in which order they started."""

    def __init__(self, gate: InferenceGate) -> None:
        self.gate = gate
        self.running = 0
        self.peak = 0
        self.started: list[int] = []
        self.release = asyncio.Event()

    async def work(self, ident: int) -> int:
        async with self.gate.slot():
            self.running += 1
            self.peak = max(self.peak, self.running)
            self.started.append(ident)
            await self.release.wait()
            self.running -= 1
            return ident


async def settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


def test_the_gate_validates_its_numbers() -> None:
    with pytest.raises(ValueError):
        InferenceGate(slots=0, max_in_flight=1, retry_after_s=1)
    with pytest.raises(ValueError):
        InferenceGate(slots=3, max_in_flight=2, retry_after_s=1)


async def test_at_most_slots_requests_run_and_the_rest_wait_in_order() -> None:
    probe = Probe(InferenceGate(slots=2, max_in_flight=4, retry_after_s=2))
    tasks = [asyncio.create_task(probe.work(i)) for i in range(4)]
    await settle()
    assert probe.running == 2
    assert probe.started == [0, 1]
    assert probe.gate.in_flight == 4
    probe.release.set()
    assert await asyncio.gather(*tasks) == [0, 1, 2, 3]
    assert probe.peak == 2
    assert probe.started == [0, 1, 2, 3]  # first come, first served
    assert probe.gate.in_flight == 0


async def test_a_request_beyond_the_limit_is_refused_at_once_with_retry_after() -> None:
    probe = Probe(InferenceGate(slots=1, max_in_flight=2, retry_after_s=3))
    tasks = [asyncio.create_task(probe.work(i)) for i in range(2)]
    await settle()
    with pytest.raises(Overloaded) as err:
        await asyncio.wait_for(probe.work(99), timeout=1)  # a regression must fail, not hang
    assert err.value.status_code == 503
    assert err.value.message_key is MessageKey.BUSY
    assert err.value.headers == {"Retry-After": "3"}
    assert 99 not in probe.started
    probe.release.set()
    await asyncio.gather(*tasks)


async def test_a_slot_freed_by_a_finished_request_admits_the_next_one() -> None:
    probe = Probe(InferenceGate(slots=1, max_in_flight=1, retry_after_s=1))
    first = asyncio.create_task(probe.work(1))
    await settle()
    with pytest.raises(Overloaded):
        await probe.work(2)
    probe.release.set()
    await first
    assert await probe.work(3) == 3


async def test_an_exception_in_the_body_frees_the_slot() -> None:
    gate = InferenceGate(slots=1, max_in_flight=1, retry_after_s=1)
    with pytest.raises(RuntimeError):
        async with gate.slot():
            raise RuntimeError("model failed")
    assert gate.in_flight == 0
    async with gate.slot():
        assert gate.in_flight == 1


async def test_a_waiting_request_that_is_cancelled_gives_its_place_back() -> None:
    probe = Probe(InferenceGate(slots=1, max_in_flight=2, retry_after_s=1))
    running = asyncio.create_task(probe.work(1))
    waiting = asyncio.create_task(probe.work(2))
    await settle()
    assert probe.gate.in_flight == 2
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    assert probe.gate.in_flight == 1
    probe.release.set()
    await running
