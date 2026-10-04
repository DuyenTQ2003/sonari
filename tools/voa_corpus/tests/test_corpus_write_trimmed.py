"""The trimmed corpus: every record can be audited line by line and undone (ADR-0008 decision 3)."""

import json
from pathlib import Path

import pytest
from voa_corpus.trim import Removed, validate
from voa_corpus.write_trimmed import DEFAULT_CAP, make_record, write

PARAGRAPHS = [
    "Share",
    "VOICE ONE: I'm Bryan Lynn.",
    "Rice is grown in many countries.",
    "Wheat is grown in colder places.",
    "I'm Anna Matteo.",
]
META = {"url": "https://example.test/a/1.html", "title": "Grains", "program": "Food", "fk": 4.2}


def test_the_default_cap_is_five_percent_as_adr_0008_says() -> None:
    assert DEFAULT_CAP == 0.05


def test_a_record_carries_the_original_the_text_and_every_removed_line() -> None:
    record = make_record(META, PARAGRAPHS, DEFAULT_CAP)
    assert record["original_text"] == PARAGRAPHS
    assert record["text"] == [PARAGRAPHS[2], PARAGRAPHS[3]]
    removed = record["trim"]["removed"]
    assert [(r["index"], r["kind"], r["text"]) for r in removed] == [
        (0, "furniture", "Share"),
        (1, "presenter", "VOICE ONE: I'm Bryan Lynn."),
        (4, "presenter", "I'm Anna Matteo."),
    ]
    assert all(r["rule"] for r in removed)


def test_a_record_names_the_rules_version_the_cap_and_the_share_cut() -> None:
    trim = make_record(META, PARAGRAPHS, DEFAULT_CAP)["trim"]
    assert trim["rules_version"].startswith("voa-trim/")
    assert trim["cap"] == DEFAULT_CAP
    assert trim["removed_words"] == 8  # furniture does not count
    assert trim["removed_share"] == pytest.approx(8 / 21, abs=1e-3)


def test_a_record_validates_and_is_undone_by_taking_the_original() -> None:
    record = make_record(META, PARAGRAPHS, DEFAULT_CAP)
    removed = [Removed(**r) for r in record["trim"]["removed"]]
    assert validate(record["original_text"], record["text"], removed) == []
    assert record["original_text"] == PARAGRAPHS  # nothing is lost


def test_writing_is_deterministic_and_the_manifest_fingerprints_the_file(tmp_path: Path) -> None:
    records = [make_record(META, PARAGRAPHS, DEFAULT_CAP)]
    snapshot = {"index_rows": 1, "index_sha256": "abc"}
    write(tmp_path / "one", records, DEFAULT_CAP, snapshot)
    write(tmp_path / "two", records, DEFAULT_CAP, snapshot)
    one, two = (tmp_path / "one" / "trimmed.jsonl"), (tmp_path / "two" / "trimmed.jsonl")
    assert one.read_bytes() == two.read_bytes()
    manifest = json.loads((tmp_path / "one" / "MANIFEST.json").read_text())
    assert manifest["passages"] == 1
    assert manifest["cap"] == DEFAULT_CAP
    assert manifest["rules_version"].startswith("voa-trim/")
    assert len(manifest["trimmed_jsonl_sha256"]) == 64
    assert json.loads(one.read_text().splitlines()[0])["url"] == META["url"]


def test_it_refuses_to_write_inside_the_cache(tmp_path: Path) -> None:
    cache = tmp_path / "voa_cache"
    cache.mkdir()
    with pytest.raises(SystemExit):
        write(cache / "out", [], DEFAULT_CAP, {}, cache=cache)
