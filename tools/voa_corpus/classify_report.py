"""`make voa-classify`: tag the trimmed corpus by type and topic safety and print the counts.

Read-only on the trimmed file (default ~/sonari-trimmed/voa/trimmed.jsonl); it writes nothing and
calls no model. `--sample N` prints a seeded sample to read by hand, shuffled and with no tag on it;
`classify_validate.py` scores the classifier against the hand labels of that sample. The method and
the results are in docs/reports/voa-classify.md.
"""

import argparse
import json
import random
from collections import Counter
from pathlib import Path

from voa_inventory.parse import _lead_paragraph

from voa_corpus.classify import (
    BODY_HITS,
    SAFETY,
    TYPES,
    USABLE_TYPES,
    classify_type,
    safety_flags,
    safety_hits,
)
from voa_corpus.measure import UNITS

DEFAULT = Path.home() / "sonari-trimmed/voa/trimmed.jsonl"
SEED = 20261007
# Reads per predicted type: most go to the explainer/news boundary, where the errors are.
ALLOC = {
    "explainer": 13, "news_item": 13, "english_teaching": 10, "dialogue_script": 4,
    "advice_column": 3, "fiction": 3, "magazine": 3, "newscast": 1,
}  # fmt: skip
RULES = {"strict": 10**9, "default": BODY_HITS, "loose": 1}  # body hits that make a flag


def load(path: Path) -> list[dict]:
    rows = []
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        lead = _lead_paragraph(r["original_text"])[:400]
        kind, rule = classify_type(r["title"], r["program"], r["text"])
        rows.append(
            {
                "id": r["url"].rsplit("/", 1)[-1].removesuffix(".html"),
                "title": r["title"].strip(),
                "type": kind,
                "rule": rule,
                "hits": safety_hits(r["title"], lead, r["text"]),
                "units": [name for name, rx in UNITS if rx.search(f"{r['title']} {lead}")],
                "as_is": all(x["kind"] == "furniture" for x in r["trim"]["removed"]),
                "raw": r,
            }
        )
    return rows


def flags(row: dict, rule: str = "default") -> frozenset[str]:
    return safety_flags(row["hits"], RULES[rule])


def usable(row: dict, rule: str = "default") -> bool:
    return row["type"] in USABLE_TYPES and not flags(row, rule)


def count(rows: list[dict], keep) -> int:
    return sum(1 for r in rows if keep(r))


def table(head: list[str], body: list[list]) -> str:
    rows = [head, ["---"] * len(head), *body]
    return "\n".join("| " + " | ".join(str(c) for c in r) + " |" for r in rows)


def report(rows: list[dict]) -> str:
    total, by_type = len(rows), Counter(r["type"] for r in rows)
    typed = [r for r in rows if r["type"] in USABLE_TYPES]
    types = [[t, by_type[t], f"{by_type[t] / total:.1%}"] for t in TYPES]
    cats = [[c, count(rows, lambda r, c=c: c in flags(r))] for c in SAFETY]
    path = [
        [k, count(rows, lambda r, k=k: bool(flags(r, k))), count(rows, lambda r, k=k: usable(r, k))]
        for k in RULES
    ]
    units = []
    for name, _ in UNITS:
        unit = [r for r in rows if name in r["units"]]
        typed_here = count(unit, lambda r: r["type"] in USABLE_TYPES)
        free = [count(unit, lambda r, k=k: usable(r, k)) for k in RULES]
        units.append([name, len(unit), typed_here, *free])
    return "\n".join(
        [
            "## Type",
            table(["type", "passages", "share"], types),
            "",
            "## Topic safety (flag: stem in title or lead, or 3+ in the body)",
            table(["category", "flagged"], [*cats, ["any", count(rows, lambda r: bool(flags(r)))]]),
            "",
            "## What the reading path can use (explainer or news item, no flag)",
            table(["flag rule", "flagged", "usable"], path),
            "",
            f"All {total} pass the level 4 filter at a cut of at most 5% (the file is that set). "
            f"As is, no cut: {count(rows, lambda r: r['as_is'])}; of those "
            f"{count(typed, lambda r: r['as_is'])} are explainer or news item and "
            f"{count(rows, lambda r: r['as_is'] and usable(r))} also carry no flag.",
            "",
            "## Per unit (a passage can match several units; crude keywords on title and lead)",
            table(
                ["unit", "tagged", "explainer/news", "no flag: strict", "default", "loose"], units
            ),
            "",
            f"Matching no unit: {count(rows, lambda r: not r['units'])}. Usable (default rule) and "
            f"tagged to a unit: {count(rows, lambda r: usable(r) and bool(r['units']))}.",
            f"Dialogue scripts: {by_type['dialogue_script']}.",
        ]
    )


def sample(rows: list[dict], seed: int = SEED) -> list[dict]:
    """A stratified sample over the predicted types, in a shuffled order that shows no type."""
    rng, picked = random.Random(seed), []
    for kind, k in ALLOC.items():
        pool = sorted((r for r in rows if r["type"] == kind), key=lambda r: r["id"])
        picked += rng.sample(pool, min(k, len(pool)))
    rng.shuffle(picked)
    return picked


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", type=Path, default=DEFAULT)
    ap.add_argument("--sample", type=int, metavar="N", help="print N passages to read, untagged")
    ap.add_argument("--tsv", action="store_true", help="one line per passage")
    a = ap.parse_args()
    rows = load(a.file)
    if a.sample:
        for r in sample(rows)[: a.sample]:
            raw = r["raw"]
            print(
                f"\n##### {r['id']} | {r['title']} | programme {raw['program']!r} | "
                f"{raw['words']} words"
            )
            print("\n".join(raw["text"]))
    elif a.tsv:
        for r in rows:
            tags = [",".join(sorted(flags(r))) or "-", ",".join(r["units"]) or "-"]
            print(r["id"], r["type"], r["rule"], *tags, int(r["as_is"]), r["title"], sep="\t")
    else:
        print(report(rows))


if __name__ == "__main__":
    main()
