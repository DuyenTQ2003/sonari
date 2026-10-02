"""Polite fetcher: robots.txt, one request per second, on-disk cache, identifying agent.

Bodies are cached as gzip files under `cache_dir`, keyed by URL hash, with an
append-only `index.jsonl` (url, file, status, fetched_at). A cached URL is never
requested again, so a crawl can stop and resume, and the parser can be re-run offline.

A multi-hour crawl must not die on one bad page. Transient errors (timeouts, connection
reset or refused, HTTP 429 and 5xx) are retried up to MAX_ATTEMPTS times with exponential
backoff and jitter, honouring Retry-After. A URL that still fails is recorded in the index
as `{"failed": true, "error": <class>, ...}` with no cache file, so a later run asks again.
Only `max_consecutive_failures` failures in a row raise CrawlAborted: that means the
network or the site is down, not one page.
"""

import gzip
import hashlib
import http.client
import json
import random
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit

from voa_inventory.robots import RobotsRules

BASE = "https://learningenglish.voanews.com"
TIMEOUT_S = 30
MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 5.0  # delays before attempts 2, 3, 4: 5, 10, 20 s, each times the jitter
MAX_RETRY_AFTER_S = 300.0  # a longer Retry-After ends the URL's attempts instead of stalling
MAX_CONSECUTIVE_FAILURES = 20
GONE = frozenset({404, 410})


class CrawlAborted(Exception):
    """Too many URLs in a row failed: the network or the site is down, not one page."""

    def __init__(self, message: str, error: str) -> None:
        super().__init__(message)
        self.error = error


class Outcome(StrEnum):
    FETCHED = "fetched"
    CACHED = "cached"
    GONE = "gone"  # 404 or 410, remembered so we do not ask again
    DISALLOWED = "disallowed"  # robots.txt
    FAILED = "failed"  # retries exhausted or a permanent error; recorded in the index


@dataclass(frozen=True)
class Fetch:
    outcome: Outcome
    body: bytes | None = None
    error: str | None = None  # class of the failure, only for FAILED


@dataclass
class Response:
    status: int
    body: bytes
    retry_after: float | None = None  # seconds, from the Retry-After header


@dataclass(frozen=True)
class Failure:
    error: str  # "TimeoutError", "ConnectionRefusedError", "HTTP503", ...
    status: int  # last HTTP status, 0 when the server never answered
    attempts: int


def parse_retry_after(value: str | None, now: float) -> float | None:
    """Seconds to wait from a Retry-After header (delta-seconds or HTTP-date), else None."""
    if value is None:
        return None
    value = value.strip()
    if value.isascii() and value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - now)


def error_class(err: BaseException) -> str:
    """Name of the root cause: urllib wraps connection errors in URLError(reason)."""
    if isinstance(err, urllib.error.URLError) and isinstance(err.reason, BaseException):
        return type(err.reason).__name__
    return type(err).__name__


def retryable(status: int) -> bool:
    return status == 429 or 500 <= status <= 599


def http_get(url: str, user_agent: str) -> Response:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return Response(resp.status, resp.read())
    except urllib.error.HTTPError as err:
        retry_after = parse_retry_after(err.headers.get("Retry-After"), time.time())
        return Response(err.code, b"", retry_after)


def random_jitter() -> float:
    return random.uniform(0.5, 1.5)


class PoliteFetcher:
    def __init__(
        self,
        cache_dir: Path,
        user_agent: str,
        min_interval_s: float = 1.0,
        get: Callable[[str, str], Response] = http_get,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random_jitter,
        max_consecutive_failures: int = MAX_CONSECUTIVE_FAILURES,
    ) -> None:
        self.cache_dir = cache_dir
        self.user_agent = user_agent
        self.min_interval_s = min_interval_s
        self._get, self._clock, self._sleep, self._jitter = get, clock, sleep, jitter
        self.max_consecutive_failures = max_consecutive_failures
        self.consecutive_failures = 0
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

    def _append_index(self, entry: dict[str, object]) -> None:
        with (self.cache_dir / "index.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    def _store(self, url: str, status: int, body: bytes) -> None:
        path = self._path(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(body))
        self._append_index(
            {"url": url, "file": path.name, "status": status, "fetched_at": time.time()}
        )

    # -- network -------------------------------------------------------------------
    def _request(self, url: str) -> Response:
        wait = self._last_request + self.min_interval_s - self._clock()
        if wait > 0:
            self._sleep(wait)
        self._last_request = self._clock()
        self.network_requests += 1
        return self._get(url, self.user_agent)

    def _download(self, url: str) -> Response | Failure:
        """A 200 or GONE response, or why `url` could not be had. Retries count as requests."""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            retry_after = None
            try:
                resp = self._request(url)
            except (OSError, http.client.HTTPException) as err:  # URLError is an OSError
                failure = Failure(error_class(err), 0, attempt)
            else:
                if resp.status == 200 or resp.status in GONE:
                    return resp
                failure = Failure(f"HTTP{resp.status}", resp.status, attempt)
                if not retryable(resp.status):
                    return failure
                retry_after = resp.retry_after
            if attempt == MAX_ATTEMPTS or (retry_after or 0) > MAX_RETRY_AFTER_S:
                return failure
            delay = max(BACKOFF_BASE_S * 2 ** (attempt - 1) * self._jitter(), retry_after or 0)
            print(f"retry {attempt}/{MAX_ATTEMPTS} {url}: {failure.error}; in {delay:.0f}s",
                  file=sys.stderr)  # fmt: skip
            self._sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover

    @property
    def robots(self) -> RobotsRules:
        if self._robots is None:
            body = self.cached(f"{BASE}/robots.txt")
            if body is None:
                result = self._download(f"{BASE}/robots.txt")
                if isinstance(result, Failure) or result.status != 200:
                    why = result.error if isinstance(result, Failure) else result.status
                    raise RuntimeError(f"robots.txt unavailable ({why}); refusing to crawl")
                self._store(f"{BASE}/robots.txt", 200, result.body)
                body = result.body
            self._robots = RobotsRules.parse(body.decode("utf-8", "replace"), self.user_agent)
        return self._robots

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        return self.robots.allowed(parts.path + (f"?{parts.query}" if parts.query else ""))

    def _record_failure(self, url: str, failure: Failure) -> Fetch:
        self._append_index({
            "url": url, "file": None, "status": failure.status, "failed": True,
            "error": failure.error, "attempts": failure.attempts, "fetched_at": time.time(),
        })  # fmt: skip
        print(f"failed {url}: {failure.error} after {failure.attempts} attempt(s); skipping",
              file=sys.stderr)  # fmt: skip
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.max_consecutive_failures:
            raise CrawlAborted(
                f"{self.consecutive_failures} consecutive URLs failed (last: {url}, "
                f"{failure.error}); the network or the site looks down",
                failure.error,
            )
        return Fetch(Outcome.FAILED, error=failure.error)

    def fetch(self, url: str) -> Fetch:
        """Get `url` from cache or the network and say what happened.

        Raises CrawlAborted when `max_consecutive_failures` URLs in a row have failed.
        """
        hit = self.cached(url)
        if hit is not None:
            return Fetch(Outcome.CACHED, hit or None)
        if not self.allowed(url):
            print(f"robots.txt disallows {url}", file=sys.stderr)
            return Fetch(Outcome.DISALLOWED)
        result = self._download(url)
        if isinstance(result, Failure):
            return self._record_failure(url, result)
        self.consecutive_failures = 0  # the site answered, so it is up
        if result.status == 200:
            self._store(url, 200, result.body)
            return Fetch(Outcome.FETCHED, result.body)
        self._store(url, result.status, b"")  # tombstone: do not ask again
        return Fetch(Outcome.GONE)

    def get(self, url: str) -> bytes | None:
        """Body of `url`, from cache or the network. None if disallowed, gone or failing."""
        return self.fetch(url).body
