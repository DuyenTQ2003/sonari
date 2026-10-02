"""Doubles for the event-bus tests: an in-memory outbox and a consumer that records."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any, ClassVar
from uuid import uuid4

from sonari_core.shared.consumer import EventConsumer
from sonari_core.shared.events import EventMessage


class SimulatedCrash(Exception):
    """Stands in for the process dying at a chosen point."""


class InMemoryOutbox:
    """Same contract as MongoOutbox, minus the transaction (see the integration tests)."""

    def __init__(self) -> None:
        self.entries: list[EventMessage] = []
        self.sent: dict[str, datetime] = {}
        self.crash_on_mark_sent = False

    def add(self, message: EventMessage) -> None:
        self.entries.append(message)

    async def unsent(self, limit: int) -> list[EventMessage]:
        return [m for m in self.entries if m.event_id not in self.sent][:limit]

    async def mark_sent(self, event_ids: Sequence[str], now: datetime) -> None:
        if self.crash_on_mark_sent:
            self.crash_on_mark_sent = False
            raise SimulatedCrash("relay died after publishing, before marking sent")
        for event_id in event_ids:
            self.sent.setdefault(event_id, now)


class RecordingConsumer(EventConsumer):
    """Counts the effect of each event; fails on demand."""

    event_type: ClassVar[str] = "TestHappened"
    group: ClassVar[str] = "test.recorder"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.effects: dict[str, int] = {}
        self.attempts: dict[str, int] = {}
        self.fail_times: dict[str, int] = {}  # event_id -> failures left before success
        self.poison: set[str] = set()  # event_ids that always fail

    async def handle(self, event_id: str, payload: dict[str, Any]) -> None:
        self.attempts[event_id] = self.attempts.get(event_id, 0) + 1
        if event_id in self.poison:
            raise ValueError(f"cannot handle {event_id}")
        if self.fail_times.get(event_id, 0) > 0:
            self.fail_times[event_id] -= 1
            raise ConnectionError("downstream is down")
        self.effects[event_id] = self.effects.get(event_id, 0) + 1


def message(event_type: str = "TestHappened", **payload: Any) -> EventMessage:
    event_id = str(uuid4())
    return EventMessage(event_id, event_type, {"eventId": event_id, **payload})
