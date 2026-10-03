"""CI runs the real-backend tests on the cmudict copy in tests/data (see tests/data/README.md)."""

import hashlib
from pathlib import Path

import pytest

from sonari_speech.g2p.backend import missing_nltk_data

NLTK_DIR = Path(__file__).resolve().parents[1] / "data" / "nltk_data"
CORPUS = NLTK_DIR / "corpora" / "cmudict"
SHA256 = {
    "cmudict": "cad209c39eb87677d64e93d97f8eed10b7e6f9bdd42de8e7ca8efc8e17d62e8a",
    "README": "b0556be7a2b12bea6a667277b75864f802dd4854480657ce298c62e6897e766b",
}


@pytest.mark.parametrize("name", sorted(SHA256))
def test_the_vendored_file_is_the_one_nltk_distributes_byte_for_byte(name: str) -> None:
    assert hashlib.sha256((CORPUS / name).read_bytes()).hexdigest() == SHA256[name]


def test_the_licence_notice_stays_with_the_data() -> None:
    notice = (CORPUS / "README").read_text(encoding="utf-8")
    assert "Carnegie Mellon University" in notice
    assert "Redistribution and use in source and binary forms" in notice


def test_the_backend_accepts_the_vendored_directory_as_its_data_dir() -> None:
    assert missing_nltk_data(NLTK_DIR) == []
