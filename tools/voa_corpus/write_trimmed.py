"""Write the trimmed corpus (ADR-0008): the passages usable at the cap, each with
the lines the parser returned, the lines left after the trim and every line removed with the rule
that removed it. Taking `original_text` undoes the trim.

    make voa-trim               # writes ~/sonari-trimmed/voa/trimmed.jsonl and MANIFEST.json

Read-only on `$DATA_DIR/voa_cache` (default `~/sonari-data`); it refuses to write inside it. The
output goes to `$TRIM_DIR` (default `~/sonari-trimmed`). Deterministic: passages are in URL order,
the JSON has sorted keys and no date, so two runs give the same bytes.
"""

import argparse
import gzip
import hashlib
import json
import os
from multiprocessing import Pool
from pathlib import Path

from voa_inventory.crawl import ARTICLE
from voa_inventory.parse import parse_page

from voa_corpus import filters
from voa_corpus.analyze import CACHE, WORDLISTS
from voa_corpus.filters import Passage
from voa_corpus.measure import init, measure
from voa_corpus.trim import rules_version, trim, validate

DEFAULT_CAP = 0.05  # ADR-0008 decision 2: a trim may cut at most this share of a passage's words
OUT = Path(os.environ.get("TRIM_DIR", "~/sonari-trimmed")).expanduser() / "voa"


def make_record(meta: dict, paragraphs: list[str], cap: float) -> dict:
    """One passage as the trimmed corpus stores it. `original_text` and `text` are lists of lines;
    `text` is `original_text` minus `trim.removed`, byte for byte and in order."""
    t = trim(paragraphs)
    problems = validate(paragraphs, t.kept, t.removed)
    if problems:
        raise ValueError(f"{meta['url']}: {'; '.join(problems)}")
    words = meta.get("words") or sum(len(p.split()) for p in paragraphs)
    return {
        **{k: meta[k] for k in ("url", "title", "program", "fk") if k in meta},
        "words": words,
        "original_text": paragraphs,
        "text": t.kept,
        "trim": {
            "rules_version": rules_version(),
            "cap": cap,
            "removed_words": t.removed_words,
            "removed_share": round(t.removed_words / words, 4) if words else 0.0,
            "removed": [
                {"index": r.index, "kind": r.kind, "rule": r.rule, "text": r.text}
                for r in t.removed
            ],
        },
    }


def write(out: Path, records: list[dict], cap: float, snapshot: dict, cache: Path = CACHE) -> None:
    if out.resolve().is_relative_to(cache.resolve()):
        raise SystemExit(f"refusing to write inside the read-only cache: {out}")
    out.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records)
    (out / "trimmed.jsonl").write_bytes(body.encode("utf-8"))
    removed = [x for r in records for x in r["trim"]["removed"]]
    manifest = {
        "cap": cap,
        "passages": len(records),
        "removed_lines": sum(x["kind"] != "furniture" for x in removed),
        "furniture_lines": sum(x["kind"] == "furniture" for x in removed),
        "removed_words": sum(r["trim"]["removed_words"] for r in records),
        "rules_version": rules_version(),
        "snapshot": snapshot,
        "trimmed_jsonl_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    (out / "MANIFEST.json").write_bytes(text.encode("utf-8"))


def usable(pages: list[Passage], cap: float) -> list[Passage]:
    """The passages the report counts at this cap: the same `blockers`, so the corpus is what the
    report says it is."""
    filters.mark_duplicates(pages)
    return [
        p
        for p in pages
        if p.words >= filters.MIN_PASSAGE_WORDS and not filters.blockers(p, cut_share=cap)
    ]


def record_of(p: Passage, cache: Path, file: str, cap: float) -> dict:
    raw = gzip.decompress((cache / file[:2] / file).read_bytes())
    item, body = parse_page(raw.decode("utf-8", "replace"), p.url)
    t = trim(body.paragraphs)
    if t.removed_words != p.removable or t.kept_frame_words != p.kept:
        raise RuntimeError(f"{p.url}: the report and the trim disagree")
    meta = {"url": p.url, "title": item.title, "program": item.program, "words": p.words}
    meta["fk"] = p.fk  # of the text left, exactly as the filter judged it
    return make_record(meta, body.paragraphs, cap)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=CACHE, help="voa_cache directory (read only)")
    parser.add_argument("--wordlist-dir", type=Path, default=WORDLISTS)
    parser.add_argument("--out", type=Path, default=OUT, help="where the trimmed corpus is written")
    parser.add_argument("--cap", type=float, default=DEFAULT_CAP, help="most that may be cut")
    args = parser.parse_args()
    index = (args.cache / "index.jsonl").read_bytes()
    entries = [json.loads(line) for line in index.decode().splitlines()]
    files = {e["url"]: e["file"] for e in entries}
    urls = sorted((e["url"], e["file"]) for e in entries if ARTICLE.match(e["url"]))
    with Pool(initializer=init, initargs=(args.cache, args.wordlist_dir)) as pool:
        pages = pool.map(measure, urls, chunksize=200)
    records = [record_of(p, args.cache, files[p.url], args.cap) for p in usable(pages, args.cap)]
    snapshot = {"index_rows": len(entries), "index_sha256": hashlib.sha256(index).hexdigest()}
    write(args.out, records, args.cap, snapshot, args.cache)
    print(f"{len(records)} passages written to {args.out}")


if __name__ == "__main__":
    main()
