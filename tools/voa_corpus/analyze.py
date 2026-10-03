"""Measure the cached VOA Learning English corpus (read-only) and print the tables of the report.

    make voa-corpus            # rewrites the GENERATED block of docs/reports/voa-corpus.md

Deterministic: pages are visited in URL order, nothing is random and the output carries no date.
It reads `$DATA_DIR/voa_cache` (default `~/sonari-data`) and writes nothing there. The word list it
needs is fetched by `make voa-wordlists`.
"""

import argparse
import hashlib
import json
import os
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

from voa_inventory.crawl import ARTICLE
from voa_inventory.levels import estimate_level

from voa_corpus import filters, wordlist
from voa_corpus.boilerplate import EDITORIAL
from voa_corpus.filters import Passage
from voa_corpus.measure import UNITS, init, measure

BEGIN, END = "<!-- BEGIN GENERATED -->", "<!-- END GENERATED -->"
CACHE = Path(os.environ.get("DATA_DIR", "~/sonari-data")).expanduser() / "voa_cache"
WORDLISTS = Path("~/.cache/sonari/wordlists").expanduser()
STEPS = (
    ("copies removed", "not a passage"),
    (f"length {filters.MIN_WORDS}-{filters.MAX_WORDS} words", "length"),
    (f"Flesch-Kincaid grade below {filters.MAX_FK:g}", "readability"),
    ("no editorial boilerplate (as is)", "boilerplate"),
    ("VOA-staff byline, no wire text (ADR-0006)", "licence"),
)


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "-"


def md(headers: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    return "\n".join(lines + ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def hist(values: list[float], edges: tuple[float, ...], unit: str = "passages") -> str:
    counts = Counter(filters.bucket(v, edges) for v in values)
    labels = [filters.bucket(e, edges) for e in (edges[0] - 1, *edges)]
    return md(
        ["bucket", unit, "share"],
        [[b, counts[b], pct(counts[b], len(values))] for b in labels],
    )


def quant(values: list[float]) -> str:
    s = sorted(values)
    return ", ".join(
        f"p{q} {s[min(len(s) - 1, len(s) * q // 100)]:.0f}" for q in (5, 25, 50, 75, 95)
    )


def top(counter: Counter[str], n: int) -> str:
    return ", ".join(
        f"{k} ({v:,})" for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:n]
    )


def row(label: str, n: int, whole: int) -> list[object]:
    return [label, n, pct(n, whole)]


def records(pages: list[Passage], text: list[Passage]) -> str:
    facts = {
        "article pages in the cache": len(pages),
        "archive unreadable or HTML cut off": sum(not p.html_ok for p in pages),
        "no article text (0 words)": sum(p.words == 0 for p in pages),
        f"passages (at least {filters.MIN_PASSAGE_WORDS} words)": len(text),
        "- identical body to an earlier page (copies)": sum(p.duplicate for p in text),
        "- VOA-staff byline, no wire text (ADR-0006)": sum(p.licence_ok for p in text),
    }
    return md(["", "pages"], list(facts.items()))


def length(pages: list[Passage], text: list[Passage]) -> str:
    words, sentences = quant([p.words for p in text]), quant([p.sentences for p in text])
    return (
        "Words per page, all article pages:\n\n"
        + hist([p.words for p in pages], filters.LENGTH_EDGES, "pages")
        + f"\n\nPassages: words {words}; sentences {sentences}."
    )


def readability(text: list[Passage]) -> str:
    below = sum((p.fk or 99) < filters.MAX_FK for p in text)
    raw_below = sum((p.fk_raw or 99) < filters.MAX_FK for p in text)
    return (
        "Flesch-Kincaid grade, without the boilerplate paragraphs (level 4 is below 7):\n\n"
        f"{hist([p.fk for p in text if p.fk is not None], filters.FK_EDGES)}\n\n"
        f"Below 7: {below} passages this way, {raw_below} with the boilerplate left in (each short "
        'line such as "Share" or "VOICE ONE:" counts as a tiny sentence).\n\n'
        "Coleman-Liau index (letters, not syllables):\n\n"
        f"{hist([p.cl for p in text if p.cl is not None], filters.FK_EDGES)}"
    )


def vocabulary(text: list[Passage]) -> str:
    totals = [sum(p.vocab[i] for p in text) for i in range(8)]
    names = [*wordlist.LEVELS, "in neither list", "proper noun or acronym"]
    rows = [[n, f"{t:,}", pct(t, sum(totals))] for n, t in zip(names, totals, strict=True)]
    unlisted: Counter[str] = Counter()
    for p in text:
        unlisted.update(p.unlisted)
    coverage = [c for p in text if (c := p.coverage) is not None]
    return (
        f"{sum(totals):,} tokens in {len(text)} passages, boilerplate paragraphs left out:\n\n"
        + md(["level", "tokens", "share"], rows)
        + "\n\nShare of each passage's tokens (proper nouns aside) at A1-B2:\n\n"
        + hist(coverage, filters.COVERAGE_EDGES)
        + f"\n\nCommonest tokens in neither list: {top(unlisted, 20)}"
    )


def boilerplate(text: list[Passage]) -> str:
    kinds = [row(k, sum(k in p.boiler for p in text), len(text)) for k in ("furniture", *EDITORIAL)]
    loose: Counter[str] = Counter()
    for p in text:
        loose.update(set(p.loose))
    editorial = hist([100 * p.editorial_words / p.words for p in text], (0.001, 2, 5, 10, 25))
    stays = sum(p.kept > 0 for p in text)
    return (
        md(["kind", "passages carrying it", "share"], kinds)
        + "\n\nFrame words on a line that stays whole (a speaker label before speech, a sign-off"
        f" glued to content; ADR-0008 never cuts these): {stays} passages"
        f" ({pct(stays, len(text))})."
        + "\n\nEditorial boilerplate (all kinds but furniture), share of a passage's words:\n\n"
        + editorial
        + f"\n\nShort paragraphs repeated most that no rule catches (recall check): {top(loose, 8)}"
    )


def funnel(text: list[Passage]) -> tuple[str, list[Passage]]:
    left, steps = [p for p in text if not p.duplicate], []
    for label, key in STEPS:
        left = [p for p in left if key not in filters.blockers(p)]
        steps.append(row(label, len(left), len(text)))
    lessons = sum(p.program.startswith(filters.LESSONS_OR_FICTION) for p in left)
    steps.append(row("- of which an English lesson or fiction programme", lessons, len(text)))
    p06 = sum(
        p.licence_ok and p.has_audio and estimate_level(p.program, p.fk_raw) == 4 for p in text
    )
    steps.append(row("For comparison, P06's 'usable level 4'", p06, len(text)))
    limits = [(0.0, "as is")] + [(c / 100, f"up to {c}% cut") for c in (2, 5, 10)]
    limits.append((1.0, "any amount"))
    grid = [
        [
            tag,
            f"{lo}-{hi}",
            *[sum(not filters.blockers(p, (lo, hi), f, share) for p in text) for f in range(6, 11)],
        ]
        for share, tag in limits
        for lo, hi in ((250, 1200), (150, 1200), (250, 2000))
    ]
    return (
        md(["step", "passages left", "of all passages"], steps)
        + "\n\nThe same filter with other thresholds (copies removed, licence required):\n\n"
        + md(["editorial boilerplate", "words", *[f"FK < {f}" for f in range(6, 11)]], grid)
    ), left


def topics(text: list[Passage], final: list[Passage]) -> str:
    light = [p for p in text if not filters.blockers(p, cut_share=0.05)]
    units = [
        [name, *[sum(i in p.units for p in group) for group in (text, final, light)]]
        for i, (name, _) in enumerate(UNITS)
    ]
    heads = ["unit (crude keywords on title and lead)", "all passages", "as is", "up to 5% cut"]
    return md(heads, units)


def render(pages: list[Passage], index_rows: int, index_sha: str) -> str:
    seen: set[str] = set()
    for p in pages:  # URL order, so the first copy of a body is the one kept
        p.duplicate = bool(p.digest) and p.digest in seen
        seen.add(p.digest)
    text = [p for p in pages if p.words >= filters.MIN_PASSAGE_WORDS]
    answer, final = funnel(text)
    sections = {
        "Records": records(pages, text),
        "Length": length(pages, text),
        "Readability": readability(text),
        "Vocabulary": vocabulary(text),
        "Boilerplate": boilerplate(text),
        "The level 4 filter": answer,
        "Topics": topics(text, final),
    }
    head = (
        f"Snapshot: `index.jsonl` {index_rows} rows (sha256 {index_sha[:12]}), {len(pages)} article"
        f" pages; word list CEFR-J 1.5 + Octanove C1/C2."
    )
    return "\n\n".join([head, *(f"### {title}\n\n{body}" for title, body in sections.items())])


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--cache", type=Path, default=CACHE, help="voa_cache directory (read only)")
    parser.add_argument("--wordlist-dir", type=Path, default=WORDLISTS)
    parser.add_argument(
        "--report", type=Path, help="markdown file whose GENERATED block is replaced"
    )
    args = parser.parse_args()
    index = (args.cache / "index.jsonl").read_bytes()
    entries = [json.loads(line) for line in index.decode().splitlines()]
    urls = sorted((e["url"], e["file"]) for e in entries if ARTICLE.match(e["url"]))
    with Pool(initializer=init, initargs=(args.cache, args.wordlist_dir)) as pool:
        pages = pool.map(measure, urls, chunksize=200)
    block = render(pages, len(entries), hashlib.sha256(index).hexdigest())
    if not args.report:
        print(block)
        return
    text = args.report.read_text("utf-8") if args.report.exists() else f"{BEGIN}\n{END}\n"
    head, rest = text.split(BEGIN, 1)
    args.report.write_text(f"{head}{BEGIN}\n{block}\n{END}{rest.split(END, 1)[1]}", "utf-8")


if __name__ == "__main__":
    main()
