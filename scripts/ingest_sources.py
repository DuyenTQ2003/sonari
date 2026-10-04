"""Ingest the trimmed VOA corpus into the content database (`content.sources`).

    make ingest-sources                         # ~/sonari-trimmed/voa/trimmed.jsonl
    make ingest-sources SOURCES_FILE=path/to/trimmed.jsonl

Idempotent: a passage is identified by its VOA article number and rules version (ADR-0010), so
a second run stores nothing twice. The file is validated whole before anything is written.
Connects as the `core` user (MONGO_URI_CORE), which may touch the content database and no
other context's. Exit status: 0 done; 1 the file is invalid or a stored version conflicts.
"""

import asyncio
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymongo import AsyncMongoClient
from sonari_core import content
from sonari_core.content.ingest import InvalidCorpus, ingest_sources, load_passages
from sonari_core.content.models import Source


def kib(size: int) -> str:
    return f"{size / 1024:.0f} KiB"


async def collection_stats(client: AsyncMongoClient[dict[str, Any]]) -> str:
    name = Source.get_pymongo_collection().name
    stats = await client[content.SPEC.context.value].command("collStats", name)
    indexes = ", ".join(f"{index} {kib(size)}" for index, size in stats["indexSizes"].items())
    return f"{name}: {stats['count']} documents, data {kib(stats['size'])}; indexes: {indexes}"


async def run(path: Path, mongo_uri: str) -> int:
    try:
        passages = load_passages(path)
    except InvalidCorpus as error:
        print(f"{path} was not ingested:", *error.problems, sep="\n  ", file=sys.stderr)
        return 1
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
        mongo_uri, tz_aware=True, serverSelectionTimeoutMS=5000
    )
    try:
        await content.SPEC.init(client)
        started = time.perf_counter()
        report = await ingest_sources(passages, datetime.now(UTC))
        seconds = time.perf_counter() - started
        print(
            f"{len(passages)} passages in {seconds:.1f}s: {report.inserted} inserted, "
            f"{report.superseded} superseded, {report.unchanged} unchanged, "
            f"{len(report.conflicts)} conflicts"
        )
        for key in report.conflicts:
            print(f"conflict: {key} is stored with different content", file=sys.stderr)
        print(await collection_stats(client))
        return 1 if report.conflicts else 0
    finally:
        await client.close()


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit("usage: ingest_sources.py PATH_TO_trimmed.jsonl")
    mongo_uri = os.environ.get("MONGO_URI_CORE")
    if not mongo_uri:
        sys.exit("MONGO_URI_CORE is not set: copy .env.example to .env and run via make")
    return asyncio.run(run(Path(sys.argv[1]), mongo_uri))


if __name__ == "__main__":
    sys.exit(main())
