"""Guard: every model in a `models.yaml` manifest must have real, fetchable URLs.

PR #26 merged with `url: null`, so nothing could download the model it pinned and its tests
could not run in CI. The service refuses a file whose SHA-256 differs from the pin, which
protects against a wrong download but says nothing about a download that is impossible. This
test runs in CI (`make test-scripts`) and fails when an entry has no `url`, an empty list, a
placeholder, or a URL that is not https and does not point at the pinned file.

A placeholder may live in a YAML comment (a TODO for a mirror that does not exist yet); it
must not be an entry of the list.
"""

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
MANIFESTS = sorted(ROOT.glob("services/*/src/**/models.yaml"))
PLACEHOLDER = re.compile(
    r"todo|tbd|fixme|changeme|placeholder|example\.|your-|xxx|<|>|\{|\}|\.\.\.|\s", re.IGNORECASE
)
SHA256 = re.compile(r"[0-9a-f]{64}")


def url_problems(entry: dict[str, Any]) -> list[str]:
    """What is wrong with the `url` list of one manifest entry; empty when it is fine."""
    urls = entry.get("url")
    if urls is None:
        return ["`url` is null or missing"]
    if not isinstance(urls, list):
        return [f"`url` must be a list of mirrors, got {type(urls).__name__}"]
    if not urls:
        return ["`url` is an empty list"]
    problems = []
    for url in urls:
        if not isinstance(url, str) or not url.strip():
            problems.append(f"empty url: {url!r}")
            continue
        if PLACEHOLDER.search(url):
            problems.append(f"placeholder url: {url}")
            continue
        parsed = urlparse(url)
        if parsed.scheme != "https" or "." not in parsed.netloc:
            problems.append(f"not an https URL with a real host: {url}")
        elif not parsed.path.endswith("/" + str(entry.get("file"))):
            problems.append(f"does not end with the pinned file name {entry.get('file')}: {url}")
    if len(set(urls)) != len(urls):
        problems.append("the same url is listed twice")
    return problems


GOOD = {
    "file": "m.onnx",
    "url": ["https://huggingface.co/owner/repo/resolve/0123abcd/m.onnx"],
}


def test_a_good_entry_has_no_problems() -> None:
    assert url_problems(GOOD) == []
    two = {**GOOD, "url": [*GOOD["url"], "https://pub-1234.r2.dev/models/m.onnx"]}
    assert url_problems(two) == []


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param({"file": "m.onnx"}, id="missing"),
        pytest.param({"file": "m.onnx", "url": None}, id="null"),
        pytest.param({"file": "m.onnx", "url": []}, id="empty list"),
        pytest.param({"file": "m.onnx", "url": [""]}, id="empty string in the list"),
        pytest.param({"file": "m.onnx", "url": [None]}, id="null in the list"),
        pytest.param({"file": "m.onnx", "url": "https://h.io/m.onnx"}, id="a bare string"),
        pytest.param({"file": "m.onnx", "url": ["https://<bucket>.r2.dev/m.onnx"]}, id="<bucket>"),
        pytest.param({"file": "m.onnx", "url": ["https://example.com/m.onnx"]}, id="example.com"),
        pytest.param({"file": "m.onnx", "url": ["https://TODO/m.onnx"]}, id="TODO"),
        pytest.param({"file": "m.onnx", "url": ["https://host.io/.../m.onnx"]}, id="ellipsis"),
        pytest.param({"file": "m.onnx", "url": ["http://host.io/m.onnx"]}, id="plain http"),
        pytest.param({"file": "m.onnx", "url": ["https://localhost/m.onnx"]}, id="no real host"),
        pytest.param({"file": "m.onnx", "url": ["https://host.io/other.onnx"]}, id="wrong file"),
        pytest.param({"file": "m.onnx", "url": [*GOOD["url"], GOOD["url"][0]]}, id="duplicate"),
        pytest.param(
            {**GOOD, "url": [*GOOD["url"], "https://r2.io/<bucket>/m.onnx"]}, id="good+bad"
        ),
    ],
)
def test_each_kind_of_missing_or_placeholder_url_is_reported(bad: dict[str, Any]) -> None:
    assert url_problems(bad) != []


def test_there_is_a_manifest_to_check() -> None:
    assert MANIFESTS, "no services/*/src/**/models.yaml found: the guard would check nothing"


@pytest.mark.parametrize("manifest", MANIFESTS, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_entry_of_every_manifest_has_real_urls_and_a_pin(manifest: Path) -> None:
    entries = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    assert entries, f"{manifest} is empty"
    for name, entry in entries.items():
        assert url_problems(entry) == [], name
        assert SHA256.fullmatch(str(entry.get("sha256"))), f"{name}: sha256 is not 64 hex digits"
        assert isinstance(entry.get("size"), int) and entry["size"] > 0, f"{name}: bad size"
