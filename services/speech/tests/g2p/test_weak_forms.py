"""The weak-form list is closed, within the model's vocabulary, and every form has a source."""

import shutil
import subprocess
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

from sonari_speech.g2p import WordPron
from sonari_speech.g2p.weak_forms import WEAK_FORMS_PATH, load_weak_forms, weak_references
from sonari_speech.phoneset.mapping import to_espeak
from sonari_speech.scoring.gop import load_vocab

CMUDICT = Path(__file__).resolve().parents[1] / "data/nltk_data/corpora/cmudict/cmudict"
CLOSED_LIST = {"to", "was", "and", "the", "a", "of", "for", "at", "can", "them"}


def espeak_version() -> str:
    if (path := shutil.which("espeak-ng")) is None:
        return ""
    return subprocess.run([path, "--version"], capture_output=True, text=True).stdout


# The phrases were read with 1.52 (weak_forms.yaml); another version may say them otherwise.
needs_espeak_152 = pytest.mark.skipif(
    "1.52" not in espeak_version(), reason="the phrases were read with espeak-ng 1.52"
)


def entries() -> list[tuple[str, dict[str, Any]]]:
    raw = yaml.safe_load(WEAK_FORMS_PATH.read_text("utf-8"))
    return [(w, e) for w, es in raw.items() if w != "version" for e in es]


def word(text: str, tokens: tuple[str, ...] = ("x",)) -> WordPron:
    return WordPron(text, 0, len(text), (), tokens, "dictionary")


@cache
def cmudict() -> dict[str, list[str]]:
    """The vendored CMUdict, word -> the phones of each variant: `TO 2 T IH0` gives "T IH0"."""
    table: dict[str, list[str]] = {}
    for line in CMUDICT.read_text("latin-1").splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) == 3:
            table.setdefault(parts[0], []).append(parts[2])
    return table


def test_the_list_is_exactly_the_ten_words_with_at_most_two_forms_each() -> None:
    forms = load_weak_forms(load_vocab().ids)
    assert set(forms) == CLOSED_LIST
    assert all(1 <= len(f) <= 2 for f in forms.values())


def test_a_form_the_model_cannot_emit_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "w.yaml"
    path.write_text('"to":\n  - tokens: t Q\n    espeak: to go\n', "utf-8")
    with pytest.raises(ValueError, match="outside the vocab"):
        load_weak_forms(load_vocab().ids, path)


def test_a_form_with_no_source_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "w.yaml"
    path.write_text('"to":\n  - tokens: t ə\n', "utf-8")
    with pytest.raises(ValueError, match="no source"):
        load_weak_forms(load_vocab().ids, path)


def test_references_are_ranked_and_a_word_without_that_rank_has_none() -> None:
    forms = {"to": (("t", "ə"), ("t", "ʊ")), "of": (("ə", "v"),)}
    words = [word("To"), word("eat"), word("of")]
    assert weak_references(words, forms) == [
        [("t", "ə"), None, ("ə", "v")],
        [("t", "ʊ"), None, None],
    ]
    assert weak_references([word("eat")], forms) == []
    assert weak_references([], forms) == []


@pytest.mark.parametrize(("target", "entry"), entries())
def test_every_form_has_a_source_and_the_checkable_ones_hold(
    target: str, entry: dict[str, Any]
) -> None:
    tokens = entry["tokens"].split()
    sources = {k: v for k, v in entry.items() if k != "tokens"}
    assert sources
    if "cmudict" in sources:
        assert sources["cmudict"] in cmudict().get(target.upper(), [])
        assert to_espeak(sources["cmudict"].split()) == tokens
    for quoted in ("wiktionary", "wikipedia"):
        if quoted in sources:
            assert "".join(tokens) in sources[quoted].replace("ˈ", "")


@needs_espeak_152
@pytest.mark.parametrize(("target", "entry"), [(w, e) for w, e in entries() if "espeak" in e])
def test_espeak_says_the_word_that_way_in_its_phrase(target: str, entry: dict[str, Any]) -> None:
    said = (
        subprocess.run(
            ["espeak-ng", "-q", "--ipa", "--sep=_", "-v", "en-us", entry["espeak"]],
            capture_output=True,
            text=True,
            check=True,
        )
        .stdout.replace("ˈ", "")
        .replace("ˌ", "")
    )
    assert "_".join(entry["tokens"].split()) in said
