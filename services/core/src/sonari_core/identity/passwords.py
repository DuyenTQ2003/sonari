"""Password hashing with argon2id.

Hashing takes tens of milliseconds of CPU, so it runs in a worker thread and never blocks
the event loop.
"""

import asyncio

from argon2 import PasswordHasher as Argon2
from argon2.exceptions import InvalidHashError, VerificationError


class PasswordHasher:
    """argon2-cffi's default hasher is argon2id with the RFC 9106 low-memory profile."""

    def __init__(self, hasher: Argon2 | None = None) -> None:
        self._hasher = hasher or Argon2()
        self._decoy: str | None = None

    async def hash(self, password: str) -> str:
        return await asyncio.to_thread(self._hasher.hash, password)

    async def verify(self, password_hash: str, password: str) -> bool:
        try:
            return await asyncio.to_thread(self._hasher.verify, password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    async def verify_unknown(self, password: str) -> None:
        """Spend the time of a real check when the account does not exist.

        Without it, "no such email" answers faster than "wrong password", which tells an
        attacker which emails are registered.
        """
        if self._decoy is None:
            self._decoy = await self.hash("decoy-for-constant-time-login")
        await self.verify(self._decoy, password)
