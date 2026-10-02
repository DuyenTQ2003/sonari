"""MongoDB-backed stores (Beanie). The atomic steps are single MongoDB operations."""

from datetime import datetime
from typing import Any

from beanie import PydanticObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from sonari_core.identity.models import RefreshTokenDocument, User
from sonari_core.identity.ports import (
    ConsumeOutcome,
    ConsumeResult,
    EmailTaken,
    TokenRecord,
    UserRecord,
)


def _user(document: User) -> UserRecord:
    return UserRecord(
        id=str(document.id),
        email=document.email,
        password_hash=document.password_hash,
        created_at=document.created_at,
    )


def _token(document: RefreshTokenDocument) -> TokenRecord:
    return TokenRecord(
        token_hash=document.token_hash,
        family_id=document.family_id,
        user_id=str(document.user_id),
        issued_at=document.issued_at,
        expires_at=document.expires_at,
        rotated_at=document.rotated_at,
        revoked_at=document.revoked_at,
    )


class MongoUserStore:
    async def create(self, email: str, password_hash: str, now: datetime) -> UserRecord:
        document = User(email=email, password_hash=password_hash, created_at=now)
        try:
            await document.insert()
        except DuplicateKeyError as error:  # the unique index decides, so there is no race
            raise EmailTaken(email) from error
        return _user(document)

    async def find_by_email(self, email: str) -> UserRecord | None:
        document = await User.find_one(User.email == email)
        return _user(document) if document else None

    async def get(self, user_id: str) -> UserRecord | None:
        if not PydanticObjectId.is_valid(user_id):
            return None
        document = await User.get(PydanticObjectId(user_id))
        return _user(document) if document else None


class MongoTokenStore:
    async def add(self, record: TokenRecord) -> None:
        await RefreshTokenDocument(
            token_hash=record.token_hash,
            family_id=record.family_id,
            user_id=PydanticObjectId(record.user_id),
            issued_at=record.issued_at,
            expires_at=record.expires_at,
        ).insert()

    async def find(self, token_hash: str) -> TokenRecord | None:
        document = await RefreshTokenDocument.find_one(
            RefreshTokenDocument.token_hash == token_hash
        )
        return _token(document) if document else None

    async def consume(self, token_hash: str, now: datetime) -> ConsumeResult:
        # One findAndModify: it matches only a token that is unspent, unrevoked and
        # unexpired, and spends it. Two concurrent callers cannot both match.
        collection = RefreshTokenDocument.get_pymongo_collection()
        spent: dict[str, Any] | None = await collection.find_one_and_update(
            {
                "token_hash": token_hash,
                "rotated_at": None,
                "revoked_at": None,
                "expires_at": {"$gt": now},
            },
            {"$set": {"rotated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if spent is not None:
            document = RefreshTokenDocument.model_validate(spent)
            return ConsumeResult(ConsumeOutcome.ROTATED, _token(document))

        existing = await self.find(token_hash)
        if existing is None:
            return ConsumeResult(ConsumeOutcome.NOT_FOUND)
        if existing.rotated_at is not None or existing.revoked_at is not None:
            return ConsumeResult(ConsumeOutcome.REUSED, existing)
        return ConsumeResult(ConsumeOutcome.EXPIRED, existing)

    async def revoke_family(self, family_id: str, now: datetime) -> None:
        await RefreshTokenDocument.get_pymongo_collection().update_many(
            {"family_id": family_id, "revoked_at": None}, {"$set": {"revoked_at": now}}
        )
