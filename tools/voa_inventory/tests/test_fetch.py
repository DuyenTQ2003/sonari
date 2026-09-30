import gzip
from itertools import pairwise
from pathlib import Path

import pytest
from voa_inventory.fetch import BASE, PoliteFetcher, RateLimited, Response

ROBOTS = b"User-agent: *\nDisallow: /comments/*\n"


class Fake:
    """Scripted server; records every request and the fake clock."""

    def __init__(self, routes: dict[str, list[Response]]) -> None:
        self.routes = routes
        self.requests: list[tuple[str, str, float]] = []
        self.now = 0.0

    def get(self, url: str, agent: str) -> Response:
        self.requests.append((url, agent, self.now))
        queue = self.routes[url]
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def fetcher(tmp_path: Path, routes: dict[str, list[Response]]) -> tuple[PoliteFetcher, Fake]:
    routes = {f"{BASE}/robots.txt": [Response(200, ROBOTS)], **routes}
    fake = Fake(routes)
    f = PoliteFetcher(
        tmp_path, "sonari-test/0.1 (contact: a@b.c)", 1.0, fake.get, fake.clock, fake.sleep
    )
    return f, fake


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


def test_server_errors_are_retried_then_dropped_without_caching(tmp_path: Path) -> None:
    url = f"{BASE}/a/flaky.html"
    f, _ = fetcher(tmp_path, {url: [Response(500, b""), Response(200, b"ok")]})
    assert f.get(url) == b"ok"
    url2 = f"{BASE}/a/dead.html"
    f, fake = fetcher(tmp_path / "b", {url2: [Response(500, b"")]})
    assert f.get(url2) is None
    assert f.cached(url2) is None
    assert [u for u, _, _ in fake.requests].count(url2) == 3


@pytest.mark.parametrize("status", [429, 503])
def test_rate_limiting_stops_the_crawl(tmp_path: Path, status: int) -> None:
    url = f"{BASE}/a/x.html"
    f, _ = fetcher(tmp_path, {url: [Response(status, b"")]})
    with pytest.raises(RateLimited):
        f.get(url)


def test_cache_files_are_gzip(tmp_path: Path) -> None:
    url = f"{BASE}/a/1.html"
    f, _ = fetcher(tmp_path, {url: [Response(200, b"hello")]})
    f.get(url)
    files = [p for p in tmp_path.rglob("*.gz")]
    assert files
    assert any(gzip.decompress(p.read_bytes()) == b"hello" for p in files)
