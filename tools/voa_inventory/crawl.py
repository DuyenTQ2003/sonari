"""Polite crawl of VOA Learning English article pages into the local cache.

    VOA_CONTACT_EMAIL=you@example.com uv run --no-project --with pyyaml \
        python -m voa_inventory.crawl --limit 3000

Article URLs come from the site's own sitemaps (robots.txt disallows the paginated
archives). They are visited in a fixed random order, so any prefix of the crawl is a
uniform random sample and a later run continues where this one stopped. Cached pages are
never requested again.
"""

import argparse
import gzip
import json
import os
import random
import re
import sys
import time
from pathlib import Path

from voa_inventory.fetch import BASE, PoliteFetcher, RateLimited

ARTICLE = re.compile(rf"^{re.escape(BASE)}/a/[^/]+(/\d+)?\.html$")
NUMBERED_SITEMAP = re.compile(r"sitemap_\d+_\d+\.xml\.gz$")
LOC = re.compile(r"<loc>(.*?)</loc>")


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "~/sonari-data")).expanduser()


def default_cache_dir() -> Path:
    return data_dir() / "voa_cache"


def user_agent() -> str:
    email = os.environ.get("VOA_CONTACT_EMAIL", "").strip()
    if "@" not in email:
        sys.exit("Set VOA_CONTACT_EMAIL to a contact address; the site owner sees it.")
    return f"sonari-voa-inventory/0.1 (research crawler, 1 req/s; contact: {email})"


def article_urls(fetcher: PoliteFetcher) -> list[str]:
    index = fetcher.get(f"{BASE}/sitemap.xml")
    if index is None:
        raise RuntimeError("sitemap.xml is unavailable")
    urls: set[str] = set()
    for sitemap in LOC.findall(index.decode("utf-8")):
        if not NUMBERED_SITEMAP.search(sitemap):
            continue
        body = fetcher.get(sitemap)
        if body is None:
            raise RuntimeError(f"{sitemap} is unavailable")
        urls.update(
            u for u in LOC.findall(gzip.decompress(body).decode("utf-8")) if ARTICLE.match(u)
        )
    return sorted(urls)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=1000, help="max new page fetches this run")
    parser.add_argument("--seed", type=int, default=1, help="order of the random sample")
    parser.add_argument("--max-minutes", type=float, default=0, help="stop after this long")
    parser.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    args = parser.parse_args()

    fetcher = PoliteFetcher(args.cache_dir, user_agent())
    urls = article_urls(fetcher)
    random.Random(args.seed).shuffle(urls)
    (args.cache_dir / "meta.json").write_text(
        json.dumps({"seed": args.seed, "sitemap_urls": len(urls), "updated": time.time()}),
        encoding="utf-8",
    )
    start, fetched, cached = time.monotonic(), 0, 0
    try:
        for url in urls:
            if fetcher.cached(url) is not None:
                cached += 1
                continue
            if fetched >= args.limit or (
                args.max_minutes and time.monotonic() - start > args.max_minutes * 60
            ):
                break
            fetcher.get(url)
            fetched += 1
            if fetched % 100 == 0:
                rate = fetched / (time.monotonic() - start)
                print(f"{fetched} fetched, {cached} already cached, {rate:.2f} pages/s", flush=True)
    except RateLimited as err:
        print(
            f"stopped: the site is rate limiting us ({err}); wait before resuming", file=sys.stderr
        )
        return 2
    print(f"done: {fetched} new pages, {cached + fetched} of {len(urls)} article URLs cached")
    return 0


if __name__ == "__main__":
    sys.exit(main())
