"""Parse the cached pages and write data/voa_inventory.csv and docs/voa-inventory.md.

    uv run --no-project --with pyyaml python -m voa_inventory.report [--tagger phrase]

Offline: it reads only the cache that `crawl` filled, so a parser or topic change is a
re-run, not a re-crawl. `--tagger embedding` needs the root project environment (torch,
transformers) and downloads bge-m3 the first time.
"""

import argparse
import json
import sys
from pathlib import Path

from voa_inventory.crawl import default_cache_dir
from voa_inventory.render import render_md
from voa_inventory.rows import Tagger, load_rows, write_csv
from voa_inventory.topics import PhraseTagger, keyword_tagger, load_catalog

REPO = Path(__file__).resolve().parents[2]
EVALUATION = Path(__file__).parent / "labels" / "evaluation.md"


def make_tagger(name: str) -> Tagger:
    if name == "phrase":
        return PhraseTagger()
    if name == "keyword-v1":
        return keyword_tagger()
    from voa_inventory.embed import EmbeddingTagger  # heavy imports only when asked for

    return EmbeddingTagger()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    parser.add_argument("--csv", type=Path, default=REPO / "data" / "voa_inventory.csv")
    parser.add_argument("--md", type=Path, default=REPO / "docs" / "voa-inventory.md")
    parser.add_argument("--tagger", choices=["phrase", "embedding", "keyword-v1"], default="phrase")
    args = parser.parse_args()
    meta_path = args.cache_dir / "meta.json"
    meta = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else {}
    tagger = make_tagger(args.tagger)
    rows = load_rows(args.cache_dir, tagger)
    write_csv(rows, args.csv)
    evaluation = EVALUATION.read_text("utf-8") if EVALUATION.exists() else ""
    args.md.write_text(
        render_md(rows, meta, load_catalog(), tagger.name, evaluation), encoding="utf-8"
    )
    print(f"{len(rows)} pages, tagger {tagger.name} -> {args.csv}, {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
