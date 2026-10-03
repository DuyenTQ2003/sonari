import functools
import hashlib
import http.server
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from sonari_speech.runtime.weights import (
    ChecksumMismatch,
    ModelSpec,
    WeightsError,
    WeightsUnavailable,
    ensure_model,
    is_valid,
    load_manifest,
    main,
    sha256_of,
)
from sonari_speech.settings import MODEL_FILE

CONTENT = b"pretend this is a 355 MB int8 model" * 100


def spec_for(content: bytes, file: str = "model.onnx", url: str | None = None) -> ModelSpec:
    return ModelSpec("test-model", file, hashlib.sha256(content).hexdigest(), len(content), url)


def host(tmp_path: Path, content: bytes = CONTENT) -> str:
    source = tmp_path / "hosted" / "model.onnx"
    source.parent.mkdir()
    source.write_bytes(content)
    return source.as_uri()


def test_the_manifest_describes_the_int8_model_the_service_loads() -> None:
    spec = load_manifest()["wav2vec2-lv-60-espeak-int8"]
    assert spec.file == MODEL_FILE
    assert len(spec.sha256) == 64
    assert int(spec.sha256, 16) >= 0
    assert spec.size > 300_000_000


def test_sha256_of_streams_a_file(tmp_path: Path) -> None:
    path = tmp_path / "f"
    path.write_bytes(CONTENT)
    assert sha256_of(path) == hashlib.sha256(CONTENT).hexdigest()


def test_a_valid_file_is_used_as_is_without_a_url(tmp_path: Path) -> None:
    (tmp_path / "model.onnx").write_bytes(CONTENT)
    assert ensure_model(spec_for(CONTENT), tmp_path) == tmp_path / "model.onnx"


def test_a_missing_file_is_downloaded_verified_and_moved_into_place(tmp_path: Path) -> None:
    target = tmp_path / "models"
    path = ensure_model(spec_for(CONTENT), target, url=host(tmp_path))
    assert path.read_bytes() == CONTENT
    assert sorted(p.name for p in target.iterdir()) == ["model.onnx"]  # no .part left behind


def test_a_download_with_the_wrong_checksum_is_refused_and_leaves_nothing(tmp_path: Path) -> None:
    target = tmp_path / "models"
    tampered = b"x" * len(CONTENT)
    with pytest.raises(ChecksumMismatch):
        ensure_model(spec_for(CONTENT), target, url=host(tmp_path, tampered))
    assert list(target.iterdir()) == []


def test_a_download_of_the_wrong_size_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "models"
    with pytest.raises(ChecksumMismatch):
        ensure_model(spec_for(CONTENT), target, url=host(tmp_path, CONTENT + b"extra"))
    assert list(target.iterdir()) == []


def test_a_corrupt_file_is_replaced_by_a_good_download(tmp_path: Path) -> None:
    target = tmp_path / "models"
    target.mkdir()
    (target / "model.onnx").write_bytes(b"truncated")
    ensure_model(spec_for(CONTENT), target, url=host(tmp_path))
    assert (target / "model.onnx").read_bytes() == CONTENT


def test_a_corrupt_file_with_no_url_is_not_used(tmp_path: Path) -> None:
    (tmp_path / "model.onnx").write_bytes(b"truncated")
    with pytest.raises(WeightsUnavailable, match="SPEECH_MODEL_URL"):
        ensure_model(spec_for(CONTENT), tmp_path)
    assert is_valid(tmp_path / "model.onnx", spec_for(CONTENT)) is False


def test_the_url_may_come_from_the_manifest(tmp_path: Path) -> None:
    spec = spec_for(CONTENT, url=host(tmp_path))
    assert ensure_model(spec, tmp_path / "models").read_bytes() == CONTENT


def test_only_http_https_and_file_urls_are_fetched(tmp_path: Path) -> None:
    with pytest.raises(WeightsError, match="scheme"):
        ensure_model(spec_for(CONTENT), tmp_path, url="ftp://example.invalid/model.onnx")


@pytest.fixture
def http_server(tmp_path: Path) -> Iterator[str]:
    (tmp_path / "served").mkdir()
    (tmp_path / "served" / "model.onnx").write_bytes(CONTENT)
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(tmp_path / "served")
    )
    handler.log_message = lambda *a, **k: None  # type: ignore[attr-defined]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/model.onnx"
    server.shutdown()
    server.server_close()


def test_a_model_is_fetched_over_http(tmp_path: Path, http_server: str) -> None:
    path = ensure_model(spec_for(CONTENT), tmp_path / "models", url=http_server)
    assert path.read_bytes() == CONTENT


def test_a_404_is_reported_as_a_weights_error_and_leaves_nothing(
    tmp_path: Path, http_server: str
) -> None:
    target = tmp_path / "models"
    with pytest.raises(WeightsError):
        ensure_model(spec_for(CONTENT), target, url=http_server.replace("model.onnx", "nope"))
    assert list(target.iterdir()) == []


def test_main_check_exits_one_when_the_model_is_missing(tmp_path: Path) -> None:
    assert main(["--check", "--dir", str(tmp_path)]) == 1


def test_main_downloads_into_the_directory_and_exits_zero(tmp_path: Path) -> None:
    manifest = tmp_path / "models.yaml"
    manifest.write_text(
        "wav2vec2-lv-60-espeak-int8:\n"
        f"  file: {MODEL_FILE}\n"
        f"  sha256: {hashlib.sha256(CONTENT).hexdigest()}\n"
        f"  size: {len(CONTENT)}\n"
    )
    out = tmp_path / "out"
    args = ["--manifest", str(manifest), "--dir", str(out), "--url", host(tmp_path)]
    assert main(args) == 0
    assert (out / MODEL_FILE).read_bytes() == CONTENT
    assert main(["--check", "--manifest", str(manifest), "--dir", str(out)]) == 0
