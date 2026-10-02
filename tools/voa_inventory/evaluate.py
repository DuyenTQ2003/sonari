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
"""

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path

from voa_inventory.crawl import default_cache_dir
from voa_inventory.rows import Row, Tagger, load_rows
from voa_inventory.sample import LABELS_CSV, SEED, SIZE
from voa_inventory.topics import Catalog, PhraseTagger, TopicMeta, keyword_tagger, load_catalog

EVALUATION = LABELS_CSV.with_name("evaluation.md")
TIE = 0.02
BETA = 0.5


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


def predictions(tagger: Tagger, rows: list[Row]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    tags = tagger.tag_all([(r.item.title, r.item.first_paragraph) for r in rows])
    urls = [r.item.url for r in rows]
    return (
        {u: set(t.topics) for u, t in zip(urls, tags, strict=True)},
        {u: set(t.candidates) for u, t in zip(urls, tags, strict=True)},
    )


def _fmt(value: float | None, num: int, den: int) -> str:
    return "n/a" if value is None else f"{value:.2f} ({num}/{den})"


def metrics_table(
    results: dict[str, dict[str, Cell]],
    metas: tuple[TopicMeta, ...],
    labels: dict[str, str],
    pool_label: str,
) -> list[str]:
    names = list(results)
    support = {t.id: sum(v == t.id for v in labels.values()) for t in metas}
    header = ["Topic", "Labelled"] + [f"{n} P" for n in names] + [f"{n} R" for n in names]
    body = []
    for t in metas:
        cells = [results[n][t.id] for n in names]
        body.append([
            f"`{t.id}`", str(support[t.id]),
            *(_fmt(c.precision, c.tp, c.tp + c.fp) for c in cells),
            *(_fmt(c.recall, c.tp, c.tp + c.fn) for c in cells),
        ])  # fmt: skip
    totals = [pooled(results[n]) for n in names]
    body.append([
        pool_label, str(sum(support.values())),
        *(_fmt(c.precision, c.tp, c.tp + c.fp) for c in totals),
        *(_fmt(c.recall, c.tp, c.tp + c.fn) for c in totals),
    ])  # fmt: skip
    body.append(["F0.5 (pooled)", "", *(f"{f_beta(c):.2f}" for c in totals), *[""] * len(names)])
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return lines + ["| " + " | ".join(r) + " |" for r in body]


def render(
    results: dict[str, dict[str, Cell]],
    candidate_results: dict[str, dict[str, Cell]],
    labels: dict[str, str],
    catalog: Catalog,
    chosen: str,
) -> str:
    plan_ids = {t.id for t in catalog.topics}
    cand_ids = {c.id for c in catalog.candidates}
    on_topic = sum(v in plan_ids for v in labels.values())
    on_candidate = sum(v in cand_ids for v in labels.values())
    none_n = len(labels) - on_topic - on_candidate
    old = pooled(results["keyword-v1"])
    lo, hi = wilson(old.tp, old.tp + old.fp)
    old_p = f"{old.precision:.2f}" if old.precision is not None else "n/a"
    plan = metrics_table(results, catalog.topics, labels, "**all 8 (pooled)**")
    cand = metrics_table(
        candidate_results, catalog.candidates, labels, "**all candidates (pooled)**"
    )
    return f"""### How the tagger was chosen

The first tagger matched bare keywords in the title and first paragraph, with no stop
patterns, and it over-counted badly. It is measured below as `keyword-v1`, only as a
baseline. Two replacements were built before any label existed, from `topics.yaml` as
committed: `phrase` (topic-specific phrases plus negative patterns) and `embedding` (bge-m3
similarity to a description per topic, similarity floor fixed in advance).

Labelled set: {len(labels)} usable level 4 pages drawn at random (seed {SEED}), labelled by
the owner with one topic or `none`: {on_topic} on one of the eight topics, {on_candidate} on a
replacement candidate, {none_n} `none`. P is precision and R recall, shown with counts
(correctly tagged / tagged, and correctly tagged / labelled). A page tagged with two topics
counts once for each. With this few pages per topic every rate is very uncertain; read the
counts.

{chr(10).join(plan)}

Replacement candidates on the same pages:

{chr(10).join(cand)}

Rule (fixed beforehand): choose the higher pooled F0.5 of `phrase` and `embedding` on the eight
plan topics, `phrase` if within {TIE}. **Chosen: `{chosen}`.**

**The earlier counts were upper bounds.** Of the pages `keyword-v1` tagged with a plan
topic, {old.tp} of {old.tp + old.fp} were correct (precision {old_p}, 95% interval
{lo:.2f}-{hi:.2f}). Every per-topic count published before this change was inflated by
the rest.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    parser.add_argument("--labels", type=Path, default=LABELS_CSV)
    args = parser.parse_args()
    catalog = load_catalog()
    ids = [t.id for t in catalog.topics]
    valid = set(ids) | {c.id for c in catalog.candidates}
    labels = load_labels(args.labels, valid)
    if len(labels) != SIZE:
        print(f"warning: {len(labels)} labelled pages, expected {SIZE}", file=sys.stderr)
    rows = [r for r in load_rows(args.cache_dir, PhraseTagger()) if r.item.url in labels]
    from voa_inventory.embed import EmbeddingTagger

    taggers = {
        "keyword-v1": keyword_tagger(),
        "phrase": PhraseTagger(),
        "embedding": EmbeddingTagger(),
    }
    results = {name: score(predictions(t, rows)[0], labels, ids) for name, t in taggers.items()}
    chosen = choose(results["phrase"], results["embedding"])
    EVALUATION.write_text(render(results, labels, catalog, chosen), encoding="utf-8")
    print(EVALUATION.read_text("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
