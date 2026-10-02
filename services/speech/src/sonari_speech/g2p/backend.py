"""g2p_en as the pronunciation backend: CMUdict for known words, a numpy GRU for the rest.

The service needs one NLTK resource, the `cmudict` corpus. g2p_en also checks for a POS
tagger when it is IMPORTED (never used here) and downloads whatever it thinks is missing,
which a service must not do at runtime, so the import runs with `nltk.download` disabled.
`G2pEnBackend` raises `G2pDataMissing` when the corpus is absent from the data directory;
`python -m sonari_speech.g2p.backend` fetches it (a build step, like the model weights).
"""

import os
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# Resource path that must exist in the data directory -> its NLTK package id.
REQUIRED = {"corpora/cmudict": "cmudict"}


class G2pDataMissing(LookupError):
    """NLTK data that the backend needs is not in the data directory."""


def default_nltk_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "~/sonari-data")).expanduser() / "nltk_data"


def missing_nltk_data(data_dir: Path) -> list[str]:
    """Resources of `REQUIRED` that are not in `data_dir` (and only there)."""
    import nltk

    missing = []
    for resource in REQUIRED:
        try:
            nltk.data.find(resource, paths=[str(data_dir)])
        except LookupError:
            missing.append(resource)
    return missing


def download_nltk_data(data_dir: Path) -> None:
    import nltk

    data_dir.mkdir(parents=True, exist_ok=True)
    for package in REQUIRED.values():
        nltk.download(package, download_dir=str(data_dir), quiet=True)


@contextmanager
def no_nltk_download() -> Iterator[None]:
    """Make `nltk.download` a no-op, so that importing g2p_en never touches the network."""
    import nltk

    original = nltk.download
    nltk.download = lambda *args, **kwargs: False
    try:
        yield
    finally:
        nltk.download = original


class G2pEnBackend:
    """Loads g2p_en once (about 2 s); `lookup` and `predict` are then cheap."""

    def __init__(self, nltk_data_dir: Path | None = None) -> None:
        data_dir = nltk_data_dir or default_nltk_dir()
        if missing := missing_nltk_data(data_dir):
            raise G2pDataMissing(
                f"{', '.join(missing)} not found in {data_dir}; "
                "run `python -m sonari_speech.g2p.backend` to download it"
            )
        import nltk

        nltk.data.path.insert(0, str(data_dir))
        with no_nltk_download():
            from g2p_en import G2p

            self._g2p: Any = G2p()

    def lookup(self, word: str) -> Sequence[str] | None:
        variants = self._g2p.cmu.get(word)
        return None if not variants else list(variants[0])

    def predict(self, word: str) -> Sequence[str]:
        return list(self._g2p.predict(word))


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else default_nltk_dir()
    download_nltk_data(target)
    print(f"NLTK data in {target}")
