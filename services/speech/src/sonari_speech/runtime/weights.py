"""Model files: pinned by SHA-256, fetched at build time, never loaded unverified.

    python -m sonari_speech.runtime.weights [--dir DIR]       # URLs from models.yaml
    SPEECH_MODEL_URL=https://... python -m sonari_speech.runtime.weights   # only this one
    python -m sonari_speech.runtime.weights --check          # exit 1 if missing or corrupt

`models.yaml` lists the mirrors of a file in order. Each is downloaded to a `.part` file next
to the target and checked against the pinned size and SHA-256; the first that matches is
renamed into place and the rest are never requested. A mirror that is down or serves a
different file is skipped, and when none matches nothing is left behind and an error names
every URL tried. So an interrupted or tampered download never leaves a model that looks usable.
"""

import argparse
import hashlib
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from sonari_speech.settings import default_model_dir

MANIFEST_PATH = Path(__file__).with_name("models.yaml")
DEFAULT_MODEL = "wav2vec2-lv-60-espeak-int8"
_SCHEMES = {"https", "http", "file"}
_CHUNK = 1 << 20

logger = logging.getLogger(__name__)


class WeightsError(RuntimeError):
    """The model file could not be obtained or did not match its pin."""


class WeightsUnavailable(WeightsError):
    """The file is missing or corrupt and there is no URL to fetch it from."""


class ChecksumMismatch(WeightsError):
    """A download did not have the pinned size or SHA-256."""


@dataclass(frozen=True, slots=True)
class ModelSpec:
    name: str
    file: str
    sha256: str
    size: int
    urls: tuple[str, ...] = ()  # mirrors, tried in order


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, ModelSpec]:
    raw = yaml.safe_load(path.read_text("utf-8")) or {}
    return {
        name: ModelSpec(name, e["file"], e["sha256"], int(e["size"]), _urls(e.get("url")))
        for name, e in raw.items()
    }


def _urls(value: str | list[str] | None) -> tuple[str, ...]:
    """The `url` field: a list of mirrors. A lone string is one URL, never its characters."""
    if value is None:
        return ()
    return (value,) if isinstance(value, str) else tuple(value)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def is_valid(path: Path, spec: ModelSpec) -> bool:
    return path.is_file() and path.stat().st_size == spec.size and sha256_of(path) == spec.sha256


def ensure_model(spec: ModelSpec, directory: Path, url: str | None = None) -> Path:
    """Path of the verified model file in `directory`, downloading it when needed.

    Sources, in order of precedence: `url`, `$SPEECH_MODEL_URL` (an operator's choice, used
    alone), then the mirrors listed in the manifest, tried one after another.
    """
    target = directory / spec.file
    if is_valid(target, spec):
        return target
    override = url or os.environ.get("SPEECH_MODEL_URL")
    sources = (override,) if override else spec.urls
    if not sources:
        raise WeightsUnavailable(
            f"{target} is missing or does not match the pinned checksum, and no URL is given: "
            "set SPEECH_MODEL_URL (or list `url` in models.yaml)"
        )
    directory.mkdir(parents=True, exist_ok=True)
    part = directory / f".{spec.file}.part"
    failures: list[WeightsError] = []
    try:
        for source in sources:
            try:
                _fetch(source, part, spec)
            except WeightsError as err:
                logger.warning("model URL skipped: %s", err)
                failures.append(err)
                continue
            os.replace(part, target)
            return target
    finally:
        part.unlink(missing_ok=True)
    raise _refused(failures)


def _refused(failures: list[WeightsError]) -> WeightsError:
    """One error for a list that gave nothing: the lone failure itself, else all of them."""
    if len(failures) == 1:
        return failures[0]
    message = "no URL gave the pinned model:\n" + "\n".join(f"  - {err}" for err in failures)
    if all(isinstance(err, ChecksumMismatch) for err in failures):
        return ChecksumMismatch(message)
    return WeightsError(message)


def _fetch(source: str, part: Path, spec: ModelSpec) -> None:
    if urllib.parse.urlparse(source).scheme not in _SCHEMES:
        raise WeightsError(f"unsupported URL scheme (use https, http or file): {source}")
    _download(source, part, spec)


def _download(source: str, part: Path, spec: ModelSpec) -> None:
    digest = hashlib.sha256()
    size = 0
    try:
        with urllib.request.urlopen(source, timeout=60) as response, part.open("wb") as out:
            while chunk := response.read(_CHUNK):
                size += len(chunk)
                if size > spec.size:
                    break  # more than the pinned size: no need to read the rest
                digest.update(chunk)
                out.write(chunk)
    except (urllib.error.URLError, OSError) as err:
        raise WeightsError(f"cannot fetch {source}: {err}") from err
    if size != spec.size or digest.hexdigest() != spec.sha256:
        raise ChecksumMismatch(
            f"{source}: expected {spec.size} bytes with sha256 {spec.sha256}, "
            f"got {size} bytes with sha256 {digest.hexdigest()}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch or verify the speech model file.")
    parser.add_argument("--dir", type=Path, default=None, help="default: SPEECH_MODEL_DIR")
    parser.add_argument(
        "--url", default=None, help="default: SPEECH_MODEL_URL, then the mirrors in the manifest"
    )
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--check", action="store_true", help="verify only; never download")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    directory = args.dir or Path(os.environ.get("SPEECH_MODEL_DIR") or default_model_dir())
    spec = load_manifest(args.manifest)[DEFAULT_MODEL]
    if args.check:
        ok = is_valid(directory / spec.file, spec)
        print(f"{directory / spec.file}: {'ok' if ok else 'missing or corrupt'}")
        return 0 if ok else 1
    try:
        print(f"ok: {ensure_model(spec, directory, args.url)}")
    except WeightsError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
