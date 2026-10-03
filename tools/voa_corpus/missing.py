"""What are the text-less VOA pages? Draw the fixed sample, count what the parser cannot read.

    make voa-missing                  # sample check, label breakdown and census (about 60 s)
    make voa-missing ARGS=--skeleton  # the drawn sample as an empty labels file

Read-only on `$DATA_DIR/voa_cache`; no network, no LLM; deterministic. Two parts:

* the sample: `SEED` picks 40 pages with no article text and 15 with 1-99 words from the URLs in
  sorted order; `docs/reports/voa-missing-labels.tsv` holds the label each got when its HTML was
  read by hand. The command checks the file still matches the draw and prints the shares with
  Wilson 95% intervals and what they imply for the whole group;
* the census, which needs no labels: the words of each page that sit inside `#article-content` but
  outside the tags `voa_inventory.parse` reads (`p`, `h2`, `h3`, `figcaption`), so the parser never
  saw them. 100 such words on a page it read as 0-99 words means the page is an article it missed.
"""

import argparse
import gzip
import json
import math
import os
import random
import re
from collections import Counter
from html.parser import HTMLParser
from multiprocessing import Pool
from pathlib import Path

from voa_inventory.crawl import ARTICLE
from voa_inventory.parse import parse_page

SEED = 20261003
SAMPLE = {"zero": 40, "short": 15}  # group -> sample size; zero = 0 words, short = 1-99 words
PASSAGE_WORDS = 100  # voa_corpus.filters.MIN_PASSAGE_WORDS
HIDDEN_WORDS = 100  # unread words that make a page an article the parser missed
CACHE = Path(os.environ.get("DATA_DIR", "~/sonari-data")).expanduser() / "voa_cache"
LABELS = Path(__file__).parents[2] / "docs/reports/voa-missing-labels.tsv"
WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
READ = {"p", "h2", "h3", "figcaption"}  # what parse.py collects
CHROME = {"li", "ul", "ol", "button", "a", "nav", "form", "select", "label", "caption", "time"}
SCRIPTS = {"script", "style", "noscript"}  # their text is code, not page text
CHROME_CLASS = ("c-mmp", "quiz", "share", "comment")  # player, quiz widget, share and comment boxes
VOID = {"br", "img", "meta", "link", "input", "hr", "source", "area", "base", "col", "embed", "wbr"}
Z = 1.96


def wilson(k: int, n: int) -> tuple[float, float]:
    """95% Wilson score interval for k successes in n trials."""
    p, z2 = k / n, Z * Z
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = Z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def draw(groups: dict[str, list[str]], seed: int = SEED) -> dict[str, list[str]]:
    """The sample: each group's URLs are sorted, then drawn with one seeded generator in order."""
    rng = random.Random(seed)
    return {g: rng.sample(sorted(groups[g]), n) for g, n in SAMPLE.items()}


class Unread(HTMLParser):
    """Words of the text nodes in #article-content that parse.py skips (text outside p/h2/h3)."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, str]] = []
        self.root: int | None = None  # stack depth of #article-content while inside it
        self.words = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in VOID:
            return
        a = dict(attrs)
        self.stack.append((tag, a.get("class") or ""))
        if a.get("id") == "article-content" and self.root is None:
            self.root = len(self.stack)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                if self.root == i + 1:
                    self.root = None
                del self.stack[i:]
                break

    def handle_data(self, data: str) -> None:
        if self.root is None or len(data.strip()) < 40:  # short nodes are labels and credits
            return
        inside = self.stack[self.root - 1 :]  # tags inside the container only
        classes = " ".join(c for _, c in inside)
        if {t for t, _ in inside} & (READ | CHROME | SCRIPTS):
            return
        if any(c in classes for c in CHROME_CLASS):
            return
        self.words += len(WORD.findall(data))


def unread_words(html: str) -> int:
    parser = Unread()
    parser.feed(html)
    return parser.words


def scan(entry: tuple[Path, str, str]) -> tuple[str, int, str, int]:
    """(url, words the parser read, title, words it never read) for one page."""
    cache, url, file = entry
    html = gzip.decompress((cache / file[:2] / file).read_bytes()).decode("utf-8", "replace")
    item, _ = parse_page(html, url)
    return url, item.word_count, item.title, unread_words(html)


def title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def md(headers: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    return "\n".join(lines + ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def read_labels(path: Path) -> list[tuple[str, str, str]]:
    rows = [line.split("\t") for line in path.read_text("utf-8").splitlines() if line.strip()]
    return [(g, url, label) for g, url, label, *_ in rows[1:]]


def breakdown(labels: list[tuple[str, str, str]], sizes: dict[str, int]) -> str:
    out = []
    for group, size in sizes.items():
        mine = Counter(label for g, _, label in labels if g == group)
        n = sum(mine.values())
        rows = []
        for label, k in sorted(mine.items(), key=lambda kv: (-kv[1], kv[0])):
            lo, hi = wilson(k, n)
            rows.append([label, f"{k}/{n}", f"{k / n:.0%}", f"{lo:.1%}-{hi:.1%}"]
                        + [f"{size * x:,.0f}" for x in (k / n, lo, hi)])  # fmt: skip
        head = ["label", "sample", "share", "95% interval", "pages (point)", "low", "high"]
        out.append(f"{group} ({size:,} pages, sample {n}):\n\n{md(head, rows)}")
    return "\n\n".join(out)


def census(rows: list[tuple[str, int, str, int]]) -> str:
    passages = {title_key(t) for _, w, t, _ in rows if w >= PASSAGE_WORDS and t}
    groups = {
        "no article text (0 words)": [r for r in rows if r[1] == 0],
        "1-99 words": [r for r in rows if 0 < r[1] < PASSAGE_WORDS],
        "passages (100+ words)": [r for r in rows if r[1] >= PASSAGE_WORDS],
    }
    table = []
    for name, group in groups.items():
        twins = sum(title_key(r[2]) in passages for r in group)
        table.append([
            name, f"{len(group):,}", sum(r[3] > 0 for r in group),
            sum(r[3] >= HIDDEN_WORDS for r in group), sum(r[3] >= 250 for r in group),
            f"{twins:,}" if name.startswith("no") else "-",
        ])  # fmt: skip
    head = ["pages", "count", "any unread text", f"unread >= {HIDDEN_WORDS} words",
            "unread >= 250 words", "same title as a passage"]  # fmt: skip
    return md(head, table)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--cache", type=Path, default=CACHE, help="voa_cache directory (read only)")
    parser.add_argument("--labels", type=Path, default=LABELS)
    parser.add_argument("--skeleton", action="store_true", help="print an empty labels file")
    args = parser.parse_args()
    index = [json.loads(x) for x in (args.cache / "index.jsonl").read_text("utf-8").splitlines()]
    entries = sorted((args.cache, e["url"], e["file"]) for e in index if ARTICLE.match(e["url"]))
    with Pool() as pool:
        rows = pool.map(scan, entries, chunksize=200)
    groups = {
        "zero": [r[0] for r in rows if r[1] == 0],
        "short": [r[0] for r in rows if 0 < r[1] < PASSAGE_WORDS],
    }
    sample = draw(groups)
    if args.skeleton:
        print("group\turl\tlabel\tevidence")
        print(*(f"{g}\t{u}\t\t" for g, urls in sample.items() for u in urls), sep="\n")
        return
    labels = read_labels(args.labels)
    if [(g, u) for g, u, _ in labels] != [(g, u) for g, urls in sample.items() for u in urls]:
        raise SystemExit(f"{args.labels} does not match the sample drawn with seed {SEED}")
    print(breakdown(labels, {g: len(urls) for g, urls in groups.items()}))
    print("\nWords inside #article-content that the parser never read:\n")
    print(census(rows))


if __name__ == "__main__":
    main()
