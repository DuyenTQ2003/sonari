"""The dev audio dump: off by default, refused in a container, complete when on."""

import json
from pathlib import Path

from tests.scoring.test_api import AUDIO, make_app, post, ready_client
from tests.support import needs_ffmpeg

from sonari_speech.scoring.dump import dump_dir
from sonari_speech.settings import Settings

DOCKERFILE = Path(__file__).parents[2] / "Dockerfile"


def test_it_is_off_unless_the_variable_is_set(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("SPEECH_DEBUG_DUMP_DIR", raising=False)
    assert Settings().debug_dump_dir is None
    assert dump_dir(None) is None


def test_it_is_refused_inside_a_container(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("container", raising=False)
    marker = tmp_path / ".dockerenv"
    assert dump_dir(tmp_path, (marker,)) == tmp_path
    marker.touch()
    assert dump_dir(tmp_path, (marker,)) is None
    monkeypatch.setenv("container", "podman")
    assert dump_dir(tmp_path, ()) is None


def test_the_image_never_sets_it() -> None:
    assert "DEBUG_DUMP" not in DOCKERFILE.read_text("utf-8")


@needs_ffmpeg
def test_each_request_is_kept_with_its_text_and_its_response(tmp_path: Path) -> None:
    app = make_app()
    app.state.dump_dir = tmp_path
    with ready_client(app) as client:
        ok = post(client, "One think you.")
        refused = post(client, "...")
    assert (ok["status"], refused["status"]) == (200, 422)

    kept = sorted(tmp_path.iterdir())
    assert len(kept) == 2
    by_text = {}
    for target in kept:
        request = json.loads((target / "request.json").read_text("utf-8"))
        by_text[request["referenceText"]] = target
        assert (target / "audio.m4a").read_bytes() == AUDIO
    response = json.loads((by_text["One think you."] / "response.json").read_text("utf-8"))
    assert response["status"] == 200 and response["body"]["referenceText"] == "One think you."
    error = json.loads((by_text["..."] / "response.json").read_text("utf-8"))
    assert error["status"] == 422
    assert error["body"]["error"]["code"] == "reference_unpronounceable"
