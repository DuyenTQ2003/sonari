"""The bounded contexts (ADR-0001) and the way a context opens its own database.

Seven contexts exist, one MongoDB database each. The core process hosts five of them;
`speech` belongs to the speech process and `tutor` to the future ai-gateway process.
A context talks to MongoDB only through the database handle of its own `ContextSpec`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from beanie import Document, init_beanie
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase


class Context(StrEnum):
    """Bounded contexts. The value is the MongoDB database name."""

    IDENTITY = "identity"
    CONTENT = "content"
    LEARNING = "learning"
    GAMIFICATION = "gamification"
    SPEECH = "speech"
    TUTOR = "tutor"
    ANALYTICS = "analytics"


CORE_CONTEXTS: Final = (
    Context.IDENTITY,
    Context.CONTENT,
    Context.LEARNING,
    Context.GAMIFICATION,
    Context.ANALYTICS,
)

MongoClient = AsyncMongoClient[dict[str, Any]]


@dataclass(frozen=True)
class ContextSpec:
    """What a context registers with the application: its name and its Beanie documents."""

    context: Context
    document_models: Sequence[type[Document]] = ()

    def database(self, client: MongoClient) -> AsyncDatabase[dict[str, Any]]:
        """The database handle of this context, and no other."""
        return client[self.context.value]

    async def init(self, client: MongoClient) -> None:
        """Bind this context's documents to its own database and create their indexes."""
        await init_beanie(
            database=self.database(client), document_models=list(self.document_models)
        )


async def init_contexts(client: MongoClient, specs: Sequence[ContextSpec]) -> None:
    """Initialise every context of the core process, one database each."""
    for spec in specs:
        if spec.context not in CORE_CONTEXTS:
            raise ValueError(f"context {spec.context.value!r} is not hosted by the core process")
    for spec in specs:
        await spec.init(client)
