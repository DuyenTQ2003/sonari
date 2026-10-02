import gzip
import http.client
import json
from collections.abc import Callable
from email.utils import formatdate
from itertools import pairwise
from pathlib import Path
from typing import Any
from urllib.error import URLError

import pytest
from voa_inventory.fetch import (
    BACKOFF_BASE_S,
    BASE,
    MAX_RETRY_AFTER_S,
    CrawlAborted,
    Outcome,
    PoliteFetcher,
    Response,
    parse_retry_after,
)

ROBOTS = b"User-agent: *\nDisallow: /comments/*\n"
URL = f"{BASE}/a/flaky.html"

# (builds the error, class name recorded in the index)
TRANSIENT_ERRORS = [
    pytest.param(
        lambda: URLError(TimeoutError("_ssl.c:1112: The handshake operation timed out")),
        "TimeoutError",
        id="handshake-timeout",
    ),
    pytest.param(
        lambda: URLError(ConnectionRefusedError(111, "Connection refused")),
        "ConnectionRefusedError",
        id="connection-refused",
    ),
    pytest.param(lambda: ConnectionResetError(104, "reset"), "ConnectionResetError", id="reset"),
    pytest.param(lambda: TimeoutError("timed out"), "TimeoutError", id="read-timeout"),
    pytest.param(
        lambda: http.client.RemoteDisconnected("closed"), "RemoteDisconnected", id="disconnected"
    ),
    pytest.param(lambda: http.client.IncompleteRead(b"par"), "IncompleteRead", id="short-read"),
    pytest.param(lambda: URLError("no host given"), "URLError", id="url-error-with-text"),
]


class Fake:
    """Scripted server; records every request and the fake clock.

    A queue item is a Response, or an exception that the transport raises.
    """

    def __init__(self, routes: dict[str, list[Response | Exception]]) -> None:
        self.routes = routes
        self.requests: list[tuple[str, str, float]] = []
        self.now = 0.0

    def get(self, url: str, agent: str) -> Response:
        self.requests.append((url, agent, self.now))
        queue = self.routes[url]
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds

    def times(self, url: str) -> list[float]:
        return [t for u, _, t in self.requests if u == url]


def fetcher(
    tmp_path: Path, routes: dict[str, list[Response | Exception]], **options: Any
) -> tuple[PoliteFetcher, Fake]:
    routes = {f"{BASE}/robots.txt": [Response(200, ROBOTS)], **routes}
    fake = Fake(routes)
    options.setdefault("jitter", lambda: 1.0)  # exact delays; jitter has its own test
    f = PoliteFetcher(
        tmp_path, "sonari-test/0.1 (contact: a@b.c)", 1.0, fake.get, fake.clock, fake.sleep,
        **options,
    )  # fmt: skip
    return f, fake


def index_entries(cache: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (cache / "index.jsonl").read_text("utf-8").splitlines()]


def test_requests_are_at_least_one_second_apart(tmp_path: Path) -> None:
    urls = [f"{BASE}/a/{i}.html" for i in range(3)]
    f, fake = fetcher(tmp_path, {u: [Response(200, b"x")] for u in urls})
    for u in urls:
        assert f.get(u) == b"x"
    times = [t for _, _, t in fake.requests]
    assert all(b - a >= 1.0 for a, b in pairwise(times))
    assert len(times) == 4  # robots.txt + 3 pages


def test_every_request_carries_the_configured_agent(tmp_path: Path) -> None:
    f, fake = fetcher(tmp_path, {f"{BASE}/a/1.html": [Response(200, b"x")]})
    f.get(f"{BASE}/a/1.html")
    assert {agent for _, agent, _ in fake.requests} == {"sonari-test/0.1 (contact: a@b.c)"}


def test_cached_pages_are_not_requested_again_even_by_a_new_fetcher(tmp_path: Path) -> None:
    url = f"{BASE}/a/1.html"
    f, _ = fetcher(tmp_path, {url: [Response(200, b"page")]})
    f.get(url)
    f2, fake2 = fetcher(tmp_path, {url: [Response(500, b"")]})
    assert f2.get(url) == b"page"
    assert [u for u, _, _ in fake2.requests] == []  # robots.txt was cached too


def test_disallowed_url_is_never_requested(tmp_path: Path) -> None:
    url = f"{BASE}/comments/9"
    f, fake = fetcher(tmp_path, {url: [Response(200, b"secret")]})
    assert f.get(url) is None
    assert url not in [u for u, _, _ in fake.requests]


def test_404_is_remembered_and_not_retried(tmp_path: Path) -> None:
    url = f"{BASE}/a/gone.html"
    f, fake = fetcher(tmp_path, {url: [Response(404, b"")]})
    assert f.get(url) is None
    assert f.get(url) is None
    assert [u for u, _, _ in fake.requests].count(url) == 1


def test_cache_files_are_gzip(tmp_path: Path) -> None:
    url = f"{BASE}/a/1.html"
    f, _ = fetcher(tmp_path, {url: [Response(200, b"hello")]})
    f.get(url)
    files = [p for p in tmp_path.rglob("*.gz")]
    assert files
    assert any(gzip.decompress(p.read_bytes()) == b"hello" for p in files)


def test_fetch_tells_cached_gone_and_disallowed_apart(tmp_path: Path) -> None:
    ok, gone, banned = f"{BASE}/a/ok.html", f"{BASE}/a/gone.html", f"{BASE}/comments/9"
    f, _ = fetcher(
        tmp_path,
        {ok: [Response(200, b"x")], gone: [Response(404, b"")], banned: [Response(200, b"s")]},
    )
    assert f.fetch(ok).outcome is Outcome.FETCHED
    assert f.fetch(ok).outcome is Outcome.CACHED
    assert f.fetch(gone).outcome is Outcome.GONE
    assert f.fetch(banned).outcome is Outcome.DISALLOWED


# -- retries ---------------------------------------------------------------------------
@pytest.mark.parametrize(("make_error", "_name"), TRANSIENT_ERRORS)
def test_a_transient_error_is_retried_and_the_page_is_cached(
    tmp_path: Path, make_error: Callable[[], Exception], _name: str
) -> None:
    f, fake = fetcher(tmp_path, {URL: [make_error(), Response(200, b"ok")]})
    result = f.fetch(URL)
    assert (result.outcome, result.body) == (Outcome.FETCHED, b"ok")
    assert len(fake.times(URL)) == 2
    assert f.cached(URL) == b"ok"


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_http_429_and_5xx_are_retried(tmp_path: Path, status: int) -> None:
    f, fake = fetcher(tmp_path, {URL: [Response(status, b""), Response(200, b"ok")]})
    assert f.get(URL) == b"ok"
    assert len(fake.times(URL)) == 2


@pytest.mark.parametrize(("make_error", "name"), TRANSIENT_ERRORS)
def test_gives_up_after_four_attempts_and_records_the_failure_in_the_index(
    tmp_path: Path, make_error: Callable[[], Exception], name: str
) -> None:
    f, fake = fetcher(tmp_path, {URL: [make_error()]})
    result = f.fetch(URL)
    assert (result.outcome, result.body, result.error) == (Outcome.FAILED, None, name)
    assert len(fake.times(URL)) == 4
    assert f.cached(URL) is None  # not cached, so a later run asks again
    entry = index_entries(tmp_path)[-1]
    assert isinstance(entry.pop("fetched_at"), float)
    assert entry == {
        "url": URL, "file": None, "status": 0, "failed": True, "error": name, "attempts": 4,
    }  # fmt: skip


def test_an_http_failure_is_recorded_with_its_status(tmp_path: Path) -> None:
    f, fake = fetcher(tmp_path, {URL: [Response(503, b"")]})
    result = f.fetch(URL)
    assert (result.outcome, result.error) == (Outcome.FAILED, "HTTP503")
    assert len(fake.times(URL)) == 4
    entry = index_entries(tmp_path)[-1]
    assert (entry["status"], entry["error"], entry["failed"]) == (503, "HTTP503", True)


def test_a_permanent_error_is_skipped_without_retrying(tmp_path: Path) -> None:
    f, fake = fetcher(tmp_path, {URL: [Response(403, b"")]})
    result = f.fetch(URL)
    assert (result.outcome, result.body, result.error) == (Outcome.FAILED, None, "HTTP403")
    assert len(fake.times(URL)) == 1
    assert index_entries(tmp_path)[-1]["error"] == "HTTP403"


def test_backoff_doubles_between_attempts(tmp_path: Path) -> None:
    f, fake = fetcher(tmp_path, {URL: [Response(503, b"")]})
    f.fetch(URL)
    gaps = [b - a for a, b in pairwise(fake.times(URL))]
    assert gaps == [BACKOFF_BASE_S, 2 * BACKOFF_BASE_S, 4 * BACKOFF_BASE_S]


def test_backoff_is_scaled_by_jitter(tmp_path: Path) -> None:
    f, fake = fetcher(tmp_path, {URL: [Response(503, b"")]}, jitter=lambda: 0.5)
    f.fetch(URL)
    gaps = [b - a for a, b in pairwise(fake.times(URL))]
    assert gaps == [0.5 * BACKOFF_BASE_S, BACKOFF_BASE_S, 2 * BACKOFF_BASE_S]


def test_retry_after_is_honoured(tmp_path: Path) -> None:
    f, fake = fetcher(tmp_path, {URL: [Response(429, b"", 60.0), Response(200, b"ok")]})
    assert f.get(URL) == b"ok"
    first, second = fake.times(URL)
    assert second - first == 60.0


def test_retry_after_shorter_than_the_backoff_does_not_shorten_it(tmp_path: Path) -> None:
    f, fake = fetcher(tmp_path, {URL: [Response(429, b"", 1.0), Response(200, b"ok")]})
    f.get(URL)
    first, second = fake.times(URL)
    assert second - first == BACKOFF_BASE_S


def test_retry_after_beyond_the_cap_gives_up_instead_of_retrying_early(tmp_path: Path) -> None:
    f, fake = fetcher(tmp_path, {URL: [Response(503, b"", MAX_RETRY_AFTER_S + 1)]})
    result = f.fetch(URL)
    assert (result.outcome, result.error) == (Outcome.FAILED, "HTTP503")
    assert len(fake.times(URL)) == 1


def test_retries_count_towards_the_one_request_per_second_limit(tmp_path: Path) -> None:
    f, fake = fetcher(tmp_path, {URL: [TimeoutError("timed out")]}, jitter=lambda: 0.0)
    f.fetch(URL)
    times = [t for _, _, t in fake.requests]
    assert len(times) == 5  # robots.txt + 4 attempts
    assert all(b - a >= 1.0 for a, b in pairwise(times))


def test_a_later_run_retries_failed_urls_but_never_refetches_cached_ones(tmp_path: Path) -> None:
    ok, bad = f"{BASE}/a/ok.html", f"{BASE}/a/bad.html"
    f, _ = fetcher(tmp_path, {ok: [Response(200, b"ok")], bad: [TimeoutError("timed out")]})
    assert f.fetch(ok).outcome is Outcome.FETCHED
    assert f.fetch(bad).outcome is Outcome.FAILED
    f2, fake2 = fetcher(tmp_path, {ok: [Response(500, b"")], bad: [Response(200, b"later")]})
    assert f2.get(ok) == b"ok"
    assert f2.get(bad) == b"later"
    assert fake2.times(ok) == []
    assert len(fake2.times(bad)) == 1


# -- giving up on the whole run --------------------------------------------------------
def test_consecutive_failures_abort_the_run_and_the_last_one_is_recorded(tmp_path: Path) -> None:
    urls = [f"{BASE}/a/{i}.html" for i in range(5)]
    f, fake = fetcher(
        tmp_path, {u: [TimeoutError("timed out")] for u in urls}, max_consecutive_failures=3
    )
    f.fetch(urls[0])
    f.fetch(urls[1])
    with pytest.raises(CrawlAborted, match="3 consecutive") as stopped:
        f.fetch(urls[2])
    assert stopped.value.error == "TimeoutError"
    assert fake.times(urls[3]) == []
    assert index_entries(tmp_path)[-1]["url"] == urls[2]


@pytest.mark.parametrize("breather", [Response(200, b"ok"), Response(404, b"")])
def test_an_answer_from_the_site_resets_the_consecutive_failure_count(
    tmp_path: Path, breather: Response
) -> None:
    bad = [f"{BASE}/a/bad{i}.html" for i in range(4)]
    mid = f"{BASE}/a/mid.html"
    routes: dict[str, list[Response | Exception]] = {u: [TimeoutError("t")] for u in bad}
    f, _ = fetcher(tmp_path, {**routes, mid: [breather]}, max_consecutive_failures=3)
    for u in (bad[0], bad[1], mid, bad[2], bad[3]):
        f.fetch(u)  # never three failures in a row, so no CrawlAborted


# -- Retry-After -----------------------------------------------------------------------
NOW = 1_700_000_000.0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("120", 120.0),
        ("0", 0.0),
        (formatdate(NOW + 90, usegmt=True), 90.0),
        (formatdate(NOW - 90, usegmt=True), 0.0),
        (None, None),
        ("soon", None),
        ("-5", None),
    ],
)
def test_parse_retry_after(value: str | None, expected: float | None) -> None:
    assert parse_retry_after(value, NOW) == expected
