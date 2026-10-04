"""Records of the trimmed VOA corpus (ADR-0008) for the content tests.

`make_record` builds what `tools/voa_corpus/write_trimmed.py` writes: the same keys, and a
`text` that is `original_text` minus the removed lines. Article numbers start far above the
real VOA ones (seven digits), so a test never touches a real source in a shared database.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

BASE_ARTICLE = 990_000_000
VERSION_A = "voa-trim/aaaaaaaaaaaa"
VERSION_B = "voa-trim/bbbbbbbbbbbb"

PRESENTER = "I’m June Simms."
FURNITURE = "Share"
BODY = [f"Sentence {number} of the test passage is short." for number in range(60)]  # 8 words each


def url_of(article: int, *, slug: str | None = None) -> str:
    middle = f"{slug}/" if slug else ""
    return f"https://learningenglish.voanews.com/a/{middle}{article}.html"


def _kind_and_rule(line: str) -> dict[str, str]:
    if line == FURNITURE:
        return {"kind": "furniture", "rule": "furniture"}
    if line == PRESENTER:
        return {"kind": "presenter", "rule": "list:presenter.txt"}
    return {"kind": "programme", "rule": "list:programme.txt"}


def make_record(
    article: int, rules_version: str = VERSION_A, *, remove: tuple[int, ...] = (0, -1)
) -> dict[str, Any]:
    """A passage whose first line is a presenter line and whose last is page furniture.

    `remove` lists the indexes to cut (negative counts from the end). A body line cut under a
    newer rules version is what a re-trim looks like.
    """
    original = [PRESENTER, *BODY, FURNITURE]
    cut = sorted({index % len(original) for index in remove})
    removed = [
        {"index": index, **_kind_and_rule(original[index]), "text": original[index]}
        for index in cut
    ]
    editorial = [line for line in original if line != FURNITURE]
    words = sum(len(line.split()) for line in editorial)
    removed_words = sum(len(r["text"].split()) for r in removed if r["kind"] != "furniture")
    return {
        "url": url_of(article),
        "title": f"Test passage {article}",
        "program": "",
        "fk": 4.2,
        "words": words,
        "original_text": original,
        "text": [line for index, line in enumerate(original) if index not in cut],
        "trim": {
            "rules_version": rules_version,
            "cap": 0.05,
            "removed_words": removed_words,
            "removed_share": round(removed_words / words, 4),
            "removed": removed,
        },
    }


def write_corpus(directory: Path, records: list[dict[str, Any]], *, manifest: bool = True) -> Path:
    """`trimmed.jsonl` as write_trimmed.py writes it, with the MANIFEST.json beside it."""
    body = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records)
    path = directory / "trimmed.jsonl"
    path.write_bytes(body.encode())
    if manifest:
        (directory / "MANIFEST.json").write_text(
            json.dumps(
                {
                    "passages": len(records),
                    "trimmed_jsonl_sha256": hashlib.sha256(body.encode()).hexdigest(),
                }
            )
        )
    return path
