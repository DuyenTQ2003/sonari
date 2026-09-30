"""Parse the cached pages and write data/voa_inventory.csv and docs/voa-inventory.md.

    uv run --no-project --with pyyaml python -m voa_inventory.report

Offline: it reads only the cache that `crawl` filled, so a parser or topic-list change
is a re-run, not a re-crawl.
"""

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from voa_inventory.crawl import ARTICLE, default_cache_dir
from voa_inventory.fetch import PoliteFetcher
from voa_inventory.levels import estimate_level
from voa_inventory.parse import Item, parse_item
from voa_inventory.topics import TopicSet, load_candidates, load_topics

REPO = Path(__file__).resolve().parents[2]
MIN_WORDS = 100  # shorter pages are captions, video stubs or menus, not source passages
LEVEL_4 = 4
NEEDED = 2
COLUMNS = [
    "url", "title", "program", "date", "byline", "has_audio", "audio_url", "word_count",
    "avg_sentence_len", "fk_grade", "est_level", "topics", "license_ok", "license_reasons",
    "credit_line", "candidate_topics",
]  # fmt: skip


@dataclass
class Row:
    item: Item
    level: int | None
    topics: dict[str, int]
    candidate_topics: dict[str, int]

    @property
    def usable(self) -> bool:
        i = self.item
        return i.license_ok and i.has_audio and i.word_count >= MIN_WORDS


def load_rows(cache_dir: Path, topics: TopicSet, candidates: TopicSet) -> list[Row]:
    fetcher = PoliteFetcher(cache_dir, "offline")
    index = cache_dir / "index.jsonl"
    urls = {}
    for line in index.read_text("utf-8").splitlines():
        entry = json.loads(line)
        if entry["status"] == 200 and ARTICLE.match(entry["url"]):
            urls[entry["url"]] = None
    rows = []
    for url in sorted(urls):
        body = fetcher.cached(url)
        if not body:
            continue
        item = parse_item(body.decode("utf-8", "replace"), url)
        level = estimate_level(item.program, item.fk_grade)
        title, para = item.title, item.first_paragraph
        rows.append(Row(item, level, topics.tag(title, para), candidates.tag(title, para)))
    return rows


def write_csv(rows: list[Row], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(COLUMNS)
        for r in rows:
            i = r.item
            writer.writerow([
                i.url, i.title, i.program, i.date, i.byline, int(i.has_audio), i.audio_url,
                i.word_count, i.avg_sentence_len, "" if i.fk_grade is None else i.fk_grade,
                "" if r.level is None else r.level, ";".join(sorted(r.topics)),
                int(i.license_ok), ";".join(i.license_reasons), i.credit_line[:200],
                ";".join(sorted(r.candidate_topics)),
            ])  # fmt: skip


def table(header: list[str], body: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
        *("| " + " | ".join(row) + " |" for row in body),
    ]


def topic_table(rows: list[Row], topics: TopicSet, coverage: float) -> tuple[list[str], list[str]]:
    lines, short = [], []
    header = [
        "Unit",
        "Topic",
        "Level 4",
        "Levels 4-5",
        "Any level",
        "Est. whole site, level 4",
        "Verdict",
    ]
    for t in topics.topics:
        pool = [r for r in rows if r.usable and t.id in r.topics]
        l4 = sum(r.level == LEVEL_4 for r in pool)
        l45 = sum(r.level in (4, 5) for r in pool)
        if l4 >= NEEDED:
            verdict = "enough"
        else:
            short.append(t.id)
            verdict = "SWAP" if coverage >= 1 else "fewer than 2 in sample"
        est = f"{l4 / coverage:.0f}" if coverage else "?"
        lines.append(
            [str(t.unit), f"{t.label} (`{t.id}`)", str(l4), str(l45), str(len(pool)), est, verdict]
        )
    return table(header, lines), short


def candidate_table(rows: list[Row], candidates: TopicSet) -> list[str]:
    ranked = []
    for t in candidates.topics:
        pool = [r for r in rows if r.usable and t.id in r.candidate_topics]
        l4 = [r for r in pool if r.level == LEVEL_4]
        ranked.append((len(l4), len(pool), t, l4 or pool))
    ranked.sort(key=lambda x: (-x[0], -x[1], x[2].id))
    body = []
    for n4, n_any, t, show in ranked:
        n45 = sum(r.usable and r.level in (4, 5) and t.id in r.candidate_topics for r in rows)
        examples = "<br>".join(f"[{r.item.title[:60]}]({r.item.url})" for r in show[:2])
        body.append([f"{t.label} (`{t.id}`)", str(n4), str(n45), str(n_any), examples])
    return table(["Candidate", "Level 4", "Levels 4-5", "Any level", "Examples"], body)


def render_md(rows: list[Row], meta: dict, topics: TopicSet, candidates: TopicSet) -> str:
    total_urls = meta.get("sitemap_urls", 0)
    coverage = len(rows) / total_urls if total_urls else 0.0
    usable = [r for r in rows if r.usable]
    would_be = [r for r in rows if r.item.has_audio and r.item.word_count >= MIN_WORDS]
    reasons = Counter(",".join(r.item.license_reasons) or "ok" for r in would_be)
    topic_lines, short = topic_table(rows, topics, coverage)
    levels: list[int | None] = [*range(1, 8), None]
    matrix = []
    for lv in levels:
        pool = [r for r in usable if r.level == lv]
        cells = [str(sum(t.id in r.topics for r in pool)) for t in topics.topics]
        untagged = sum(not r.topics for r in pool)
        matrix.append([str(lv or "unknown"), *cells, str(untagged), str(len(pool))])
    programs = Counter(r.item.program or "(none)" for r in rows)
    prog_usable = Counter(r.item.program or "(none)" for r in usable)
    prog_rows = [[p, str(n), str(prog_usable[p])] for p, n in programs.most_common(15)]
    swap = "\n".join(f"- `{t}`" for t in short) or "- none"
    partial = (
        f"""**Partial crawl.** Only {coverage:.1%} of the site is sampled. "Fewer than 2 in
sample" therefore does not show that the corpus lacks items, only that this sample is too
small to show them; "SWAP" appears only at 100% coverage. Continue with `make voa-crawl`."""
        if coverage < 1
        else ""
    )
    return f"""# VOA Learning English inventory

Generated by `python -m voa_inventory.report` on {date.today().isoformat()}; do not edit by
hand. Metadata only: `data/voa_inventory.csv` holds one row per page (URL, title, dates,
counts, flags), never article text or audio.

## Coverage

- The site's sitemaps list **{total_urls}** article URLs. This inventory parsed
  **{len(rows)}** of them (**{coverage:.1%}**), visited in a fixed random order
  (seed {meta.get("seed", "?")}), so the sample is uniform and every count below is a lower
  bound on the whole site. "Est. whole site" divides by the coverage: a rough scale, not a
  count.
- Pages with text of at least {MIN_WORDS} words and audio: {len(would_be)}.
  **Usable** (also licence_ok): **{len(usable)}**.

**Usable** means: VOA-staff byline, no wire credit or mention (AP, Reuters, AFP), no
third-party image credit, an audio file on the page, and at least {MIN_WORDS} words of body text.
The filter is conservative on purpose (`license.py`); P50 re-checks every item it ingests.

Licence outcome of the {len(would_be)} pages with audio and enough text:

{chr(10).join(table(["Reasons", "Pages"], [[k, str(v)] for k, v in reasons.most_common()]))}

## Level 4 candidate topics

Level is a coarse heuristic (`levels.py`): *Let's Learn English* lessons by programme
level, everything else by Flesch-Kincaid grade (below 7 is level 4, 7-9 level 5, 9-11
level 6, above level 7). Topics are keyword tags on title and first paragraph
(`topics.yaml`), so they over-count. Counts are usable items.

{chr(10).join(topic_lines)}

### Topics with fewer than {NEEDED} usable items with audio at level 4

{swap}

{partial}

ADR-0006: a topic without items is swapped, never written. Replacement candidates,
scored the same way (usable items in the sample; examples are level 4, else any level):

{chr(10).join(candidate_table(rows, candidates))}

## Level by topic (usable items)

{chr(10).join(table(["Level", *[t.id for t in topics.topics], "no topic", "Total"], matrix))}

An item can carry several topics, so a row can sum to more than its total.

## Programmes (top 15 by pages)

{chr(10).join(table(["Programme", "Pages", "Usable"], prog_rows))}

## Reproduce

```bash
export VOA_CONTACT_EMAIL=you@example.com   # sent in the User-Agent
make voa-crawl ARGS="--limit 3000"         # resumable, 1 request per second
make voa-report                            # offline; rewrites this file and the CSV
```
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    parser.add_argument("--csv", type=Path, default=REPO / "data" / "voa_inventory.csv")
    parser.add_argument("--md", type=Path, default=REPO / "docs" / "voa-inventory.md")
    args = parser.parse_args()
    meta_path = args.cache_dir / "meta.json"
    meta = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else {}
    topics, candidates = load_topics(), load_candidates()
    rows = load_rows(args.cache_dir, topics, candidates)
    write_csv(rows, args.csv)
    args.md.write_text(render_md(rows, meta, topics, candidates), encoding="utf-8")
    print(f"{len(rows)} pages -> {args.csv}, {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
