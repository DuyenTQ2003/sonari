from collections import Counter
from pathlib import Path

import pytest
from voa_inventory.crawl import Summary, crawl_urls, print_summary
from voa_inventory.fetch import BASE, PoliteFetcher, Response


class Site:
    """Scripted site: url -> Response, or an exception the transport raises."""

    def __init__(self, pages: dict[str, Response | Exception]) -> None:
        self.pages = pages
        self.requested: list[str] = []

    def get(self, url: str, agent: str) -> Response:
        self.requested.append(url)
        if url.endswith("/robots.txt"):
            return Response(200, b"")  # allow everything
        page = self.pages[url]
        if isinstance(page, Exception):
            raise page
        return page


def crawler(
    tmp_path: Path, pages: dict[str, Response | Exception], max_failures: int = 20
) -> tuple[PoliteFetcher, Site]:
    site = Site(pages)
    f = PoliteFetcher(
        tmp_path, "test", 0.0, get=site.get, sleep=lambda _s: None, jitter=lambda: 1.0,
        max_consecutive_failures=max_failures,
    )  # fmt: skip
    return f, site


def page(i: int) -> str:
    return f"{BASE}/a/{i}.html"


def test_a_url_that_keeps_failing_is_skipped_and_the_crawl_continues(tmp_path: Path) -> None:
    pages = {page(1): Response(200, b"a"), page(2): TimeoutError("t"), page(3): Response(200, b"c")}
    f, site = crawler(tmp_path, pages)
    summary = crawl_urls(f, list(pages), limit=10)
    assert (summary.fetched, summary.failed, summary.aborted) == (2, 1, None)
    assert summary.failures == Counter({"TimeoutError": 1})
    assert site.requested.count(page(3)) == 1


def test_the_crawl_stops_after_n_consecutive_failures(tmp_path: Path) -> None:
    pages: dict[str, Response | Exception] = {page(i): TimeoutError("t") for i in range(6)}
    f, site = crawler(tmp_path, pages, max_failures=3)
    summary = crawl_urls(f, list(pages), limit=10)
    assert summary.failed == 3
    assert summary.aborted is not None
    assert "3 consecutive" in summary.aborted
    assert page(3) not in site.requested


def test_cached_urls_are_counted_and_never_requested(tmp_path: Path) -> None:
    pages: dict[str, Response | Exception] = {page(1): Response(200, b"a")}
    crawl_urls(crawler(tmp_path, pages)[0], list(pages), limit=10)
    f, site = crawler(tmp_path, pages)
    summary = crawl_urls(f, list(pages), limit=10)
    assert (summary.cached, summary.fetched) == (1, 0)
    assert page(1) not in site.requested


def test_the_limit_counts_every_attempt_including_failed_ones(tmp_path: Path) -> None:
    pages = {page(1): TimeoutError("t"), page(2): Response(200, b"b"), page(3): Response(200, b"c")}
    f, site = crawler(tmp_path, pages)
    summary = crawl_urls(f, list(pages), limit=2)
    assert (summary.failed, summary.fetched) == (1, 1)
    assert page(3) not in site.requested


def test_the_summary_gives_the_counts_and_the_failure_classes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    summary = Summary(fetched=120, cached=15907, gone=1)
    summary.failures.update({"TimeoutError": 2, "HTTP503": 1})
    print_summary(summary)
    out = capsys.readouterr()
    assert "fetched 120, cached 15907, gone 1, disallowed 0, failed 3" in out.out
    assert "HTTP503=1, TimeoutError=2" in out.out
    assert out.err == ""


def test_an_aborted_run_says_why_and_that_it_can_be_resumed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    print_summary(Summary(aborted="20 consecutive URLs failed (last: HTTP503)"))
    err = capsys.readouterr().err
    assert "stopped: 20 consecutive URLs failed" in err
    assert "run it again" in err
