"""`scripts/ingest_sources.py` end to end on the real MongoDB, in a process of its own, the way
`make ingest-sources` runs it: environment in, exit code and one summary line out."""

import os
import random
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pymongo import MongoClient

from source_fakes import BASE_ARTICLE, VERSION_B, make_record, write_corpus

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "ingest_sources.py"


def run_script(path: Path, mongo_uri: str, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path), *flags],
        env={**os.environ, "MONGO_URI_CORE": mongo_uri},
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture
def numbers(mongo_client: MongoClient[dict[str, Any]]) -> Iterator[list[int]]:
    """Three article numbers no real VOA page has; what the test wrote is deleted after."""
    issued = random.sample(range(BASE_ARTICLE, BASE_ARTICLE + 9_000_000), 3)
    yield issued
    mongo_client["content"]["sources"].delete_many(
        {"source_id": {"$in": [f"voa:{n}" for n in issued]}}
    )


def count(client: MongoClient[dict[str, Any]], numbers: list[int]) -> int:
    ids = [f"voa:{n}" for n in numbers]
    return client["content"]["sources"].count_documents({"source_id": {"$in": ids}})


def test_running_the_script_twice_leaves_the_same_documents(
    core_mongo_uri: str,
    mongo_client: MongoClient[dict[str, Any]],
    numbers: list[int],
    tmp_path: Path,
) -> None:
    corpus = write_corpus(tmp_path, [make_record(n) for n in numbers])

    first = run_script(corpus, core_mongo_uri)
    second = run_script(corpus, core_mongo_uri)

    assert (first.returncode, second.returncode) == (0, 0), first.stderr + second.stderr
    assert "3 inserted, 0 superseded, 0 unchanged, 0 conflicts" in first.stdout
    assert "0 inserted, 0 superseded, 3 unchanged, 0 conflicts" in second.stdout
    assert count(mongo_client, numbers) == 3


def test_the_script_reports_the_collection_it_wrote(
    core_mongo_uri: str, numbers: list[int], tmp_path: Path
) -> None:
    corpus = write_corpus(tmp_path, [make_record(n) for n in numbers])

    result = run_script(corpus, core_mongo_uri)

    assert "sources:" in result.stdout
    assert "source_id_current" in result.stdout  # index sizes are part of the report


def test_a_bad_file_is_refused_and_nothing_is_written(
    core_mongo_uri: str,
    mongo_client: MongoClient[dict[str, Any]],
    numbers: list[int],
    tmp_path: Path,
) -> None:
    records = [make_record(n) for n in numbers]
    records[1]["text"] = records[1]["text"][1:]  # no longer the original minus the removed lines

    result = run_script(write_corpus(tmp_path, records), core_mongo_uri)

    assert result.returncode == 1
    assert "line 2" in result.stderr
    assert count(mongo_client, numbers) == 0  # the two good lines were not written either


def test_a_conflicting_version_fails_the_run_and_names_the_key(
    core_mongo_uri: str,
    mongo_client: MongoClient[dict[str, Any]],
    numbers: list[int],
    tmp_path: Path,
) -> None:
    run_script(write_corpus(tmp_path, [make_record(n) for n in numbers]), core_mongo_uri)
    changed = make_record(numbers[0])
    changed["title"] = "Same rules version, different title"
    other = tmp_path / "second"
    other.mkdir()

    result = run_script(write_corpus(other, [changed]), core_mongo_uri)

    assert result.returncode == 1
    assert f"conflict: voa:{numbers[0]}@" in result.stderr
    assert count(mongo_client, numbers) == 3


def test_a_new_rules_version_through_the_script_supersedes_and_keeps_the_old(
    core_mongo_uri: str,
    mongo_client: MongoClient[dict[str, Any]],
    numbers: list[int],
    tmp_path: Path,
) -> None:
    run_script(write_corpus(tmp_path, [make_record(n) for n in numbers]), core_mongo_uri)
    newer = tmp_path / "newer"
    newer.mkdir()
    retrimmed = write_corpus(newer, [make_record(n, VERSION_B, remove=(0, 1, -1)) for n in numbers])

    result = run_script(retrimmed, core_mongo_uri)

    assert result.returncode == 0, result.stderr
    assert "0 inserted, 3 superseded, 0 unchanged, 0 conflicts" in result.stdout
    assert count(mongo_client, numbers) == 6


def test_a_dry_run_says_what_would_happen_and_writes_nothing(
    core_mongo_uri: str,
    mongo_client: MongoClient[dict[str, Any]],
    numbers: list[int],
    tmp_path: Path,
) -> None:
    corpus = write_corpus(tmp_path, [make_record(n) for n in numbers])

    dry = run_script(corpus, core_mongo_uri, "--dry-run")
    real = run_script(corpus, core_mongo_uri)

    assert dry.returncode == 0, dry.stderr
    assert "dry run, nothing written" in dry.stdout
    assert "3 would be inserted, 0 would be superseded, 0 unchanged, 0 conflicts" in dry.stdout
    assert "3 inserted, 0 superseded, 0 unchanged, 0 conflicts" in real.stdout  # what it promised
    assert count(mongo_client, numbers) == 3  # all written by the real run, none by the dry one


def test_a_dry_run_against_stored_passages_counts_them_as_unchanged(
    core_mongo_uri: str,
    mongo_client: MongoClient[dict[str, Any]],
    numbers: list[int],
    tmp_path: Path,
) -> None:
    corpus = write_corpus(tmp_path, [make_record(n) for n in numbers])
    run_script(corpus, core_mongo_uri)
    before = list(mongo_client["content"]["sources"].find({}).sort("_id"))

    dry = run_script(corpus, core_mongo_uri, "--dry-run")

    assert dry.returncode == 0, dry.stderr
    assert "0 would be inserted, 0 would be superseded, 3 unchanged, 0 conflicts" in dry.stdout
    assert list(mongo_client["content"]["sources"].find({}).sort("_id")) == before


def test_a_dry_run_that_finds_a_conflict_exits_1_and_names_the_key(
    core_mongo_uri: str,
    mongo_client: MongoClient[dict[str, Any]],
    numbers: list[int],
    tmp_path: Path,
) -> None:
    run_script(write_corpus(tmp_path, [make_record(n) for n in numbers]), core_mongo_uri)
    changed = make_record(numbers[0])
    changed["title"] = "Same rules version, different title"
    other = tmp_path / "second"
    other.mkdir()

    dry = run_script(write_corpus(other, [changed]), core_mongo_uri, "--dry-run")

    assert dry.returncode == 1  # so a dry run can gate the real one in a shell `&&`
    assert f"conflict: voa:{numbers[0]}@" in dry.stderr
    assert count(mongo_client, numbers) == 3


def test_a_bad_file_is_refused_the_same_way_in_a_dry_run(
    core_mongo_uri: str, numbers: list[int], tmp_path: Path
) -> None:
    records = [make_record(n) for n in numbers]
    records[1]["text"] = records[1]["text"][1:]

    dry = run_script(write_corpus(tmp_path, records), core_mongo_uri, "--dry-run")

    assert dry.returncode == 1
    assert "line 2" in dry.stderr
