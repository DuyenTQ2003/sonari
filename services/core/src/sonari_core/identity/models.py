"""Beanie documents of the identity database."""

from datetime import datetime
from typing import Annotated, ClassVar

from beanie import Document, Indexed, PydanticObjectId
from pymongo import ASCENDING, IndexModel


class User(Document):
    email: Annotated[str, Indexed(unique=True)]  # stored lower-case
    password_hash: str
    created_at: datetime

    class Settings:
        name = "users"


class RefreshTokenDocument(Document):
    token_hash: Annotated[str, Indexed(unique=True)]  # SHA-256 of the token, never the token
    family_id: Annotated[str, Indexed()]
    user_id: PydanticObjectId
    issued_at: datetime
    expires_at: datetime
    rotated_at: datetime | None = None
    revoked_at: datetime | None = None

    class Settings:
        name = "refresh_tokens"
        # MongoDB deletes a token once it has expired; it could not be used any more.
        indexes: ClassVar[list[IndexModel]] = [
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0)
        ]
