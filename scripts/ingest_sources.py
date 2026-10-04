"""Ingest the trimmed VOA corpus into the content database (`content.sources`).

    make ingest-sources                         # ~/sonari-trimmed/voa/trimmed.jsonl
    make ingest-sources SOURCES_FILE=path/to/trimmed.jsonl
    make ingest-sources ARGS=--dry-run          # say what would happen, write nothing

Idempotent: a passage is identified by its VOA article number and rules version (ADR-0010), so
a second run stores nothing twice. The file is validated whole before anything is written.
Connects as the `core` user (MONGO_URI_CORE), which may touch the content database and no
other context's.

`--dry-run` reads the stored versions and prints the counts the real run would print, with no
transaction, no write and no index created. It is a forecast, not a lock. The summary and the exit
status are the real run's: a conflict is named and exits 1, so a dry run can gate the real one.

Exit status: 0 done; 1 the file is invalid or a stored version conflicts.
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymongo import AsyncMongoClient
from sonari_core import content
from sonari_core.content.ingest import (
    IngestReport,
    InvalidCorpus,
    bind_read_only,
    ingest_sources,
    load_passages,
    plan_sources,
)
from sonari_core.content.models import Source


def kib(size: int) -> str:
    return f"{size / 1024:.0f} KiB"


async def collection_stats(client: AsyncMongoClient[dict[str, Any]]) -> str:
    name = Source.get_pymongo_collection().name
    stats = await client[content.SPEC.context.value].command("collStats", name)
    indexes = ", ".join(f"{index} {kib(size)}" for index, size in stats["indexSizes"].items())
    return f"{name}: {stats['count']} documents, data {kib(stats['size'])}; indexes: {indexes}"


def summary(report: IngestReport, passages: int, seconds: float, dry_run: bool) -> str:
    prefix, would = ("dry run, nothing written: ", "would be ") if dry_run else ("", "")
    return (
        f"{prefix}{passages} passages in {seconds:.1f}s: {report.inserted} {would}inserted, "
        f"{report.superseded} {would}superseded, {report.unchanged} unchanged, "
        f"{len(report.conflicts)} conflicts"
    )


async def run(path: Path, mongo_uri: str, dry_run: bool) -> int:
    try:
        passages = load_passages(path)
    except InvalidCorpus as error:
        print(f"{path} was not ingested:", *error.problems, sep="\n  ", file=sys.stderr)
        return 1
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
        mongo_uri, tz_aware=True, serverSelectionTimeoutMS=5000
    )
    try:
        # `SPEC.init` creates the indexes, which on an empty database creates the collection too.
        if dry_run:
            await bind_read_only(content.SPEC.database(client))
        else:
            await content.SPEC.init(client)
        started = time.perf_counter()
        if dry_run:
            report = await plan_sources(passages)
        else:
            report = await ingest_sources(passages, datetime.now(UTC))
        seconds = time.perf_counter() - started
        print(summary(report, len(passages), seconds, dry_run))
        for key in report.conflicts:
            print(f"conflict: {key} is stored with different content", file=sys.stderr)
        if not dry_run:
            print(await collection_stats(client))
        return 1 if report.conflicts else 0
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest the trimmed VOA corpus (ADR-0010).")
    parser.add_argument("path", type=Path, help="the trimmed.jsonl that `make voa-trim` writes")
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would happen and write nothing"
    )
    args = parser.parse_args()
    mongo_uri = os.environ.get("MONGO_URI_CORE")
    if not mongo_uri:
        sys.exit("MONGO_URI_CORE is not set: copy .env.example to .env and run via make")
    return asyncio.run(run(args.path, mongo_uri, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
