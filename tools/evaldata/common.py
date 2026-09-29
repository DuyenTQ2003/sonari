"""Shared paths for evaluation-data tools. All data lives under DATA_DIR, never in the repo."""

import os
from pathlib import Path


def data_dir() -> Path:
    """Return DATA_DIR (env var), defaulting to ~/sonari-data."""
    return Path(os.environ.get("DATA_DIR", "~/sonari-data")).expanduser()


def librispeech_dir() -> Path:
    return data_dir() / "librispeech"
