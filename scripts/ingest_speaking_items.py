"""Ingest the practice sentences into the content database (`content.speaking_items`).

    make ingest-speaking-items                      # tools/speaking_items/items.jsonl

Run `make ingest-sources` first: every item pins a stored Source (ADR-0010) and ingest checks the
sentence is there unchanged (ADR-0006). Idempotent: an item's `_id` is its source, line and offset,
so a second run stores nothing twice. The file is validated whole, and checked against the Sources,
before anything is written. Connects as the `core` user (MONGO_URI_CORE).

Exit status: 0 done; 1 the file is invalid, a pinned Source is missing or differs, or a stored item
conflicts.
"""

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymongo import AsyncMongoClient
from sonari_core import content
from sonari_core.content.ingest import InvalidCorpus
from sonari_core.content.speaking_ingest import ingest_items, load_items, source_problems


async def run(path: Path, mongo_uri: str) -> int:
    try:
        items = load_items(path)
    except InvalidCorpus as error:
        print(f"{path} was not ingested:", *error.problems, sep="\n  ", file=sys.stderr)
        return 1
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
        mongo_uri, tz_aware=True, serverSelectionTimeoutMS=5000
    )
    try:
        await content.SPEC.init(client)
        if problems := await source_problems(items):
            print(f"{path} was not ingested:", *problems, sep="\n  ", file=sys.stderr)
            return 1
        report = await ingest_items(items, datetime.now(UTC))
        print(
            f"{len(items)} items: {report.inserted} inserted, {report.unchanged} unchanged, "
            f"{len(report.conflicts)} conflicts"
        )
        for key in report.conflicts:
            print(f"conflict: {key} is stored with different content", file=sys.stderr)
        return 1 if report.conflicts else 0
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest the practice sentences (ADR-0006).")
    parser.add_argument("path", type=Path, help="the items.jsonl that `make speaking-items` writes")
    args = parser.parse_args()
    mongo_uri = os.environ.get("MONGO_URI_CORE")
    if not mongo_uri:
        sys.exit("MONGO_URI_CORE is not set: copy .env.example to .env and run via make")
    return asyncio.run(run(args.path, mongo_uri))


if __name__ == "__main__":
    sys.exit(main())
