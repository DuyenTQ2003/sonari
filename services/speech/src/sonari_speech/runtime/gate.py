"""Bounded concurrency for inference.

At most `slots` requests run at once; up to `max_in_flight` (running plus waiting) are
admitted, and the next one is refused at once with 503 and `Retry-After`, instead of
joining a queue that makes every request slow (P20). The numbers come from BENCH.md.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator

from sonari_speech.errors import AppError, MessageKey


class Overloaded(AppError):
    """The service is at capacity: try again after `retry_after_s` seconds."""

    def __init__(self, retry_after_s: int) -> None:
        super().__init__(
            503,
            "busy",
            MessageKey.BUSY,
            {"retryAfterS": retry_after_s},
            {"Retry-After": str(retry_after_s)},
        )


class InferenceGate:
    def __init__(self, slots: int, max_in_flight: int, retry_after_s: int) -> None:
        if slots < 1 or max_in_flight < slots:
            raise ValueError("need 1 <= slots <= max_in_flight")
        self._max_in_flight = max_in_flight
        self._retry_after_s = retry_after_s
        self._semaphore = asyncio.Semaphore(slots)  # waiters are woken first come, first served
        self._in_flight = 0

    @property
    def in_flight(self) -> int:
        return self._in_flight

    @contextlib.asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Hold one inference slot; raises `Overloaded` instead of waiting when full."""
        if self._in_flight >= self._max_in_flight:
            raise Overloaded(self._retry_after_s)
        self._in_flight += 1
        try:
            async with self._semaphore:
                yield
        finally:
            self._in_flight -= 1
