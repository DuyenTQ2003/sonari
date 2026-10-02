"""What the auth service needs from storage, as plain types.

The service depends on these protocols, not on Beanie, so its rules (rotation, reuse
detection) are tested in CI against in-memory stores and against MongoDB locally.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


@dataclass(frozen=True)
class UserRecord:
    id: str
    email: str
    password_hash: str
    created_at: datetime


@dataclass(frozen=True)
class TokenRecord:
    """One refresh token. All tokens of one login chain share a `family_id`."""

    token_hash: str
    family_id: str
    user_id: str
    issued_at: datetime
    expires_at: datetime
    rotated_at: datetime | None = None
    revoked_at: datetime | None = None


class ConsumeOutcome(StrEnum):
    ROTATED = "rotated"  # valid and now spent: the caller issues its successor
    REUSED = "reused"  # was already spent or revoked: someone replayed it
    EXPIRED = "expired"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class ConsumeResult:
    outcome: ConsumeOutcome
    record: TokenRecord | None = None


class EmailTaken(Exception):
    """An account with this email exists."""


class UserStore(Protocol):
    async def create(self, email: str, password_hash: str, now: datetime) -> UserRecord:
        """Raises EmailTaken. The check and the insert must be one atomic step."""
        ...

    async def find_by_email(self, email: str) -> UserRecord | None: ...

    async def get(self, user_id: str) -> UserRecord | None: ...


class TokenStore(Protocol):
    async def add(self, record: TokenRecord) -> None: ...

    async def find(self, token_hash: str) -> TokenRecord | None: ...

    async def consume(self, token_hash: str, now: datetime) -> ConsumeResult:
        """Spend a token exactly once.

        Of any number of concurrent calls with the same valid token, exactly one gets
        ROTATED; the rest get REUSED.
        """
        ...

    async def revoke_family(self, family_id: str, now: datetime) -> None: ...
