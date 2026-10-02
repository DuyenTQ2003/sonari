"""Polite crawl of VOA Learning English article pages into the local cache.

    VOA_CONTACT_EMAIL=you@example.com uv run --no-project --with pyyaml \
        python -m voa_inventory.crawl --limit 3000

Article URLs come from the site's own sitemaps (robots.txt disallows the paginated
archives). They are visited in a fixed random order, so any prefix of the crawl is a
uniform random sample and a later run continues where this one stopped. Cached pages are
never requested again. A page that keeps failing is recorded in the index and skipped; a
later run tries it again. The run stops only after many URLs in a row fail.
"""

import argparse
import gzip
import json
import os
import random
import re
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from voa_inventory.fetch import (
    BASE,
    MAX_CONSECUTIVE_FAILURES,
    CrawlAborted,
    Outcome,
    PoliteFetcher,
)

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


@dataclass
class Summary:
    fetched: int = 0
    cached: int = 0
    gone: int = 0
    disallowed: int = 0
    failures: Counter[str] = field(default_factory=Counter)  # error class -> URLs
    aborted: str | None = None  # why the run stopped early, if it did

    @property
    def failed(self) -> int:
        return sum(self.failures.values())


def crawl_urls(
    fetcher: PoliteFetcher,
    urls: list[str],
    limit: int,
    out_of_time: Callable[[], bool] = lambda: False,
) -> Summary:
    """Visit `urls` in order. `limit` counts every attempt, failed ones included."""
    summary, attempts, start = Summary(), 0, time.monotonic()
    for url in urls:
        if fetcher.cached(url) is not None:
            summary.cached += 1
            continue
        if attempts >= limit or out_of_time():
            break
        attempts += 1
        try:
            result = fetcher.fetch(url)
        except CrawlAborted as err:
            summary.failures[err.error] += 1
            summary.aborted = str(err)
            break
        if result.outcome is Outcome.FETCHED:
            summary.fetched += 1
        elif result.outcome is Outcome.GONE:
            summary.gone += 1
        elif result.outcome is Outcome.DISALLOWED:
            summary.disallowed += 1
        elif result.error is not None:
            summary.failures[result.error] += 1
        if attempts % 100 == 0:
            rate = attempts / (time.monotonic() - start)
            print(
                f"{attempts} attempted, {summary.fetched} fetched, {summary.failed} failed, "
                f"{summary.cached} already cached, {rate:.2f} pages/s",
                flush=True,
            )
    return summary


def print_summary(summary: Summary) -> None:
    if summary.aborted:
        print(
            f"stopped: {summary.aborted}. Fix the connection or wait, then run it again: "
            "cached pages are skipped and failed URLs are retried.",
            file=sys.stderr,
        )
    print(
        f"summary: fetched {summary.fetched}, cached {summary.cached}, gone {summary.gone}, "
        f"disallowed {summary.disallowed}, failed {summary.failed}"
    )
    if summary.failures:
        classes = ", ".join(f"{name}={n}" for name, n in sorted(summary.failures.items()))
        print(f"failure classes: {classes}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=1000, help="max page attempts this run")
    parser.add_argument("--seed", type=int, default=1, help="order of the random sample")
    parser.add_argument("--max-minutes", type=float, default=0, help="stop after this long")
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=MAX_CONSECUTIVE_FAILURES,
        help="stop the run after this many URLs in a row fail (network or site down)",
    )
    parser.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    args = parser.parse_args()

    fetcher = PoliteFetcher(
        args.cache_dir, user_agent(), max_consecutive_failures=args.max_consecutive_failures
    )
    urls = article_urls(fetcher)
    random.Random(args.seed).shuffle(urls)
    (args.cache_dir / "meta.json").write_text(
        json.dumps({"seed": args.seed, "sitemap_urls": len(urls), "updated": time.time()}),
        encoding="utf-8",
    )
    start = time.monotonic()
    summary = crawl_urls(
        fetcher,
        urls,
        args.limit,
        lambda: bool(args.max_minutes) and time.monotonic() - start > args.max_minutes * 60,
    )
    print_summary(summary)
    print(f"{summary.cached + summary.fetched} of {len(urls)} article URLs cached")
    return 2 if summary.aborted else 0


if __name__ == "__main__":
    sys.exit(main())
