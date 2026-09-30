"""Polite fetcher: robots.txt, one request per second, on-disk cache, identifying agent.

Bodies are cached as gzip files under `cache_dir`, keyed by URL hash, with an
append-only `index.jsonl` (url, file, status, fetched_at). A cached URL is never
requested again, so a crawl can stop and resume, and the parser can be re-run offline.
"""

import gzip
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from voa_inventory.robots import RobotsRules

BASE = "https://learningenglish.voanews.com"
TIMEOUT_S = 30
RETRIES = 2
GONE = frozenset({404, 410})


class RateLimited(Exception):
    """The site asked us to slow down (429 or 503). Stop the crawl; do not retry."""


@dataclass
class Response:
    status: int
    body: bytes


def http_get(url: str, user_agent: str) -> Response:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return Response(resp.status, resp.read())
    except urllib.error.HTTPError as err:
        return Response(err.code, b"")


class PoliteFetcher:
    def __init__(
        self,
        cache_dir: Path,
        user_agent: str,
        min_interval_s: float = 1.0,
        get: Callable[[str, str], Response] = http_get,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cache_dir = cache_dir
        self.user_agent = user_agent
        self.min_interval_s = min_interval_s
        self._get, self._clock, self._sleep = get, clock, sleep
        self._last_request = -min_interval_s
        self._robots: RobotsRules | None = None
        self.network_requests = 0
        cache_dir.mkdir(parents=True, exist_ok=True)

    # -- cache ---------------------------------------------------------------------
    def _path(self, url: str) -> Path:
        digest = hashlib.sha1(url.encode(), usedforsecurity=False).hexdigest()
        return self.cache_dir / digest[:2] / f"{digest}.gz"

    def cached(self, url: str) -> bytes | None:
        path = self._path(url)
        return gzip.decompress(path.read_bytes()) if path.exists() else None

    def _store(self, url: str, status: int, body: bytes) -> None:
        path = self._path(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(body))
        entry = {"url": url, "file": path.name, "status": status, "fetched_at": time.time()}
        with (self.cache_dir / "index.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    # -- network -------------------------------------------------------------------
    def _request(self, url: str) -> Response:
        wait = self._last_request + self.min_interval_s - self._clock()
        if wait > 0:
            self._sleep(wait)
        self._last_request = self._clock()
        self.network_requests += 1
        return self._get(url, self.user_agent)

    @property
    def robots(self) -> RobotsRules:
        if self._robots is None:
            body = self.cached(f"{BASE}/robots.txt")
            if body is None:
                resp = self._request(f"{BASE}/robots.txt")
                if resp.status != 200:
                    raise RuntimeError(f"robots.txt returned {resp.status}; refusing to crawl")
                self._store(f"{BASE}/robots.txt", 200, resp.body)
                body = resp.body
            self._robots = RobotsRules.parse(body.decode("utf-8", "replace"), self.user_agent)
        return self._robots

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        return self.robots.allowed(parts.path + (f"?{parts.query}" if parts.query else ""))

    def get(self, url: str) -> bytes | None:
        """Body of `url`, from cache or the network. None if disallowed, gone or failing."""
        hit = self.cached(url)
        if hit is not None:
            return hit or None
        if not self.allowed(url):
            print(f"robots.txt disallows {url}", file=sys.stderr)
            return None
        for attempt in range(RETRIES + 1):
            resp = self._request(url)
            if resp.status == 200:
                self._store(url, 200, resp.body)
                return resp.body
            if resp.status in GONE:
                self._store(url, resp.status, b"")  # tombstone: do not ask again
                return None
            if resp.status in (429, 503):
                raise RateLimited(f"{resp.status} for {url}")
            self._sleep(5 * (attempt + 1))
        print(f"giving up on {url} after {RETRIES + 1} tries", file=sys.stderr)
        return None
