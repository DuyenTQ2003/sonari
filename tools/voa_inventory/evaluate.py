"""Score the taggers against the owner's labels and pick one.

    PYTHONPATH=tools uv run python -m voa_inventory.evaluate

Labels: labels/topic_labels.csv (n, url, title, label), one label per page: a topic id, a
candidate id, or `none`. Writes labels/evaluation.md, which the report embeds.

Selection rule, fixed before any label existed: among the phrase and embedding taggers,
choose the higher micro F0.5 over the eight plan topics (precision counts twice as much as
recall, because the report is used to confirm that a topic HAS items and false positives are
what inflate that). If the two are within TIE of each other, choose the phrase tagger: it is
deterministic and needs no model. The old keyword tagger is measured but never selected.
Nothing is tuned after the numbers appear: thresholds and lists come from topics.yaml as
committed before the sample was drawn.

Reporting rule, fixed before any tagger was scored on the labels: a topic gets a precision
and recall only with at least MIN_SUPPORT labelled pages; below that the report shows raw
counts and says the sample is too small. Macro averages run over those topics only.
"""

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

from voa_inventory.crawl import default_cache_dir
from voa_inventory.rows import LEVEL_4, Row, Tagger, load_rows
from voa_inventory.sample import LABELS_CSV, SIZE
from voa_inventory.topics import PhraseTagger, keyword_tagger, load_catalog

EVALUATION = LABELS_CSV.with_name("evaluation.md")
TIE = 0.02
BETA = 0.5
MIN_SUPPORT = 10
PREFIX = "keyword-v1 on pre-fix text"


@dataclass(frozen=True)
class Cell:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float | None:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else None

    @property
    def recall(self) -> float | None:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None


def load_labels(path: Path, valid: set[str]) -> dict[str, str]:
    """url -> label. Fails loudly on a blank or unknown label rather than guessing."""
    labels = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            label = row["label"].strip()
            if label != "none" and label not in valid:
                raise ValueError(f"row {row['n']}: label {label!r} is blank or not a known topic")
            labels[row["url"]] = label
    return labels


def score(
    predicted: dict[str, set[str]], labels: dict[str, str], ids: list[str]
) -> dict[str, Cell]:
    """Per-topic counts. A page counts once per topic it is tagged with."""
    cells = {}
    for topic in ids:
        tp = sum(topic in predicted[u] and labels[u] == topic for u in labels)
        fp = sum(topic in predicted[u] and labels[u] != topic for u in labels)
        fn = sum(topic not in predicted[u] and labels[u] == topic for u in labels)
        cells[topic] = Cell(tp, fp, fn)
    return cells


def pooled(cells: dict[str, Cell]) -> Cell:
    return Cell(
        sum(c.tp for c in cells.values()),
        sum(c.fp for c in cells.values()),
        sum(c.fn for c in cells.values()),
    )


def measurable(labels: dict[str, str], ids: list[str]) -> list[str]:
    """Topics with enough labelled pages for a rate to mean anything."""
    return [t for t in ids if sum(v == t for v in labels.values()) >= MIN_SUPPORT]


def macro(cells: dict[str, Cell], ids: list[str]) -> tuple[float | None, float | None]:
    """Unweighted mean precision and recall over `ids`; an undefined precision counts as 0."""
    if not ids:
        return None, None
    p = sum(cells[t].precision or 0.0 for t in ids) / len(ids)
    r = sum(cells[t].recall or 0.0 for t in ids) / len(ids)
    return p, r


def f_beta(cell: Cell, beta: float = BETA) -> float:
    p, r = cell.precision, cell.recall
    if not p or not r:
        return 0.0
    return (1 + beta**2) * p * r / (beta**2 * p + r)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for k successes in n trials."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def choose(phrase: dict[str, Cell], embedding: dict[str, Cell]) -> str:
    """The declared selection rule; returns "phrase" or "embedding"."""
    fp, fe = f_beta(pooled(phrase)), f_beta(pooled(embedding))
    return "embedding" if fe - fp > TIE else "phrase"


def predictions(tagger: Tagger, rows: list[Row], prefix: bool = False) -> dict[str, set[str]]:
    """url -> every topic and candidate id the tagger gives the page.

    `prefix` feeds the first paragraph the extractor returned before the placeholder fix.
    """
    tags = tagger.tag_all([
        (r.item.title, r.item.prefix_first_paragraph if prefix else r.item.first_paragraph)
        for r in rows
    ])  # fmt: skip
    return {r.item.url: set(t.topics) | set(t.candidates) for r, t in zip(rows, tags, strict=True)}


@dataclass(frozen=True)
class Corpus:
    """Size of the pool the labelled sample was drawn from."""

    usable_level4: int
    coverage: float  # parsed pages / sitemap URLs


def corpus(rows: list[Row], cache_dir: Path) -> Corpus:
    meta_path = cache_dir / "meta.json"
    meta = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else {}
    total = meta.get("sitemap_urls", 0)
    return Corpus(
        sum(r.usable and r.level == LEVEL_4 for r in rows), len(rows) / total if total else 0.0
    )


def main() -> int:
    from voa_inventory.evaluate_render import render

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    parser.add_argument("--labels", type=Path, default=LABELS_CSV)
    args = parser.parse_args()
    catalog = load_catalog()
    ids = [t.id for t in catalog.topics] + [c.id for c in catalog.candidates]
    labels = load_labels(args.labels, set(ids))
    if len(labels) != SIZE:
        print(f"warning: {len(labels)} labelled pages, expected {SIZE}", file=sys.stderr)
    all_rows = load_rows(args.cache_dir, PhraseTagger())
    rows = [r for r in all_rows if r.item.url in labels]
    missing = set(labels) - {r.item.url for r in rows}
    if missing:
        sys.exit(f"{len(missing)} labelled URLs are not in the cache, e.g. {sorted(missing)[0]}")
    from voa_inventory.embed import EmbeddingTagger

    old = keyword_tagger()
    predicted = {
        PREFIX: predictions(old, rows, prefix=True),
        "keyword-v1": predictions(old, rows),
        "phrase": predictions(PhraseTagger(), rows),
        "embedding": predictions(EmbeddingTagger(), rows),
    }
    results = {name: score(p, labels, ids) for name, p in predicted.items()}
    plan = [t.id for t in catalog.topics]
    chosen = choose(
        {t: results["phrase"][t] for t in plan}, {t: results["embedding"][t] for t in plan}
    )
    # Pages whose pre-fix first paragraph was boilerplate rather than article text.
    placeholder = sum(r.item.prefix_first_paragraph != r.item.first_paragraph for r in rows)
    text = render(results, labels, catalog, chosen, corpus(all_rows, args.cache_dir), placeholder)
    EVALUATION.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
