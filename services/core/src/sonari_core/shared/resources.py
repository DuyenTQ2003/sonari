"""The process's connections to MongoDB and Redis, and the readiness checks over them."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from pymongo import AsyncMongoClient
from redis.asyncio import Redis

from sonari_core.shared.contexts import MongoClient
from sonari_core.shared.settings import Settings


class ReadinessCheck(Protocol):
    """Raises when the dependency cannot serve traffic."""

    async def ping(self) -> None: ...


class MongoReadiness:
    def __init__(self, client: MongoClient) -> None:
        self._client = client

    async def ping(self) -> None:
        await self._client["admin"].command("ping")


class RedisReadiness:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def ping(self) -> None:
        await self._redis.ping()


@dataclass
class Resources:
    """What `/readyz` probes, plus the clients themselves when they are real.

    Tests build one from fakes with no clients. `mongo` is None then, so the Beanie
    initialisation, which needs a live database, is skipped.
    """

    readiness: Mapping[str, ReadinessCheck]
    mongo: MongoClient | None = None
    redis: Redis | None = None

    async def close(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()
        if self.mongo is not None:
            await self.mongo.close()


def build_resources(settings: Settings) -> Resources:
    """Create the real clients. Neither connects until first use."""
    mongo: MongoClient = AsyncMongoClient(
        settings.mongo_uri,
        serverSelectionTimeoutMS=settings.mongo_server_selection_timeout_ms,
        tz_aware=True,
    )
    redis: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return Resources(
        readiness={"mongo": MongoReadiness(mongo), "redis": RedisReadiness(redis)},
        mongo=mongo,
        redis=redis,
    )
