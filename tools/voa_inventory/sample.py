"""Draw the labelled evaluation sample: usable level 4 pages, random, fixed seed.

    PYTHONPATH=tools uv run --no-project --with pyyaml python -m voa_inventory.sample

Writes tools/voa_inventory/labels/topic_labels.csv (n, url, title, empty label) for the owner
to fill in, and DATA_DIR/voa_inventory/label_sheet.md with each page's title and first
paragraph. The repo keeps titles and labels only, never article text.
"""

import argparse
import csv
import random
import sys
from pathlib import Path

from voa_inventory.crawl import data_dir, default_cache_dir
from voa_inventory.rows import LEVEL_4, Row, load_rows
from voa_inventory.topics import PhraseTagger, load_catalog

LABELS_DIR = Path(__file__).parent / "labels"
LABELS_CSV = LABELS_DIR / "topic_labels.csv"
SEED = 20260930
SIZE = 100


def draw(rows: list[Row], size: int = SIZE, seed: int = SEED) -> list[Row]:
    """`size` usable level 4 rows: sorted by URL, then sampled with a fixed seed."""
    pool = sorted((r for r in rows if r.usable and r.level == LEVEL_4), key=lambda r: r.item.url)
    return random.Random(seed).sample(pool, min(size, len(pool)))


def write_template(sample: list[Row], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["n", "url", "title", "label"])
        for n, r in enumerate(sample, start=1):
            writer.writerow([n, r.item.url, r.item.title, ""])


def sheet(sample: list[Row], width: int = 320) -> str:
    catalog = load_catalog()
    ids = [*(t.id for t in catalog.topics), *(c.id for c in catalog.candidates)]
    lines = ["Valid labels: " + ", ".join(ids) + ", none", ""]
    for n, r in enumerate(sample, start=1):
        para = r.item.first_paragraph
        lines.append(f"{n}. {r.item.title}\n   {para[:width]}{'...' if len(para) > width else ''}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    parser.add_argument("--size", type=int, default=SIZE)
    args = parser.parse_args()
    # Tagging is irrelevant here; the cheap tagger only satisfies load_rows.
    rows = load_rows(args.cache_dir, PhraseTagger())
    sample = draw(rows, args.size)
    if LABELS_CSV.exists() and any(
        row["label"] for row in csv.DictReader(LABELS_CSV.open(encoding="utf-8"))
    ):
        sys.exit(f"{LABELS_CSV} already holds labels; not overwriting")
    write_template(sample, LABELS_CSV)
    out = data_dir() / "voa_inventory"
    out.mkdir(parents=True, exist_ok=True)
    (out / "label_sheet.md").write_text(sheet(sample), encoding="utf-8")
    print(f"{len(sample)} pages -> {LABELS_CSV}\nsheet -> {out / 'label_sheet.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
