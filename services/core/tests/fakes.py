"""Test doubles shared by the unit tests."""

import asyncio
from collections.abc import Callable

from fastapi import FastAPI


class FakeCheck:
    """A readiness check that succeeds, fails, or hangs on demand."""

    def __init__(self, *, error: Exception | None = None, delay_s: float = 0.0) -> None:
        self.error = error
        self.delay_s = delay_s

    async def ping(self) -> None:
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.error is not None:
            raise self.error


AppFactory = Callable[..., FastAPI]
