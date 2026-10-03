from pathlib import Path

import pytest
import yaml

from sonari_speech.g2p.lexicon import LEXICON_PATH, load_lexicon
from sonari_speech.phoneset.mapping import to_espeak


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "lexicon.yaml"
    path.write_text(text, "utf-8")
    return path


def test_the_shipped_lexicon_loads_and_has_the_p03_syllable_count_fixes() -> None:
    lexicon = load_lexicon()
    assert lexicon["every"] == ["EH1", "V", "R", "IY0"]
    assert lexicon["different"] == ["D", "IH1", "F", "R", "AH0", "N", "T"]


def test_every_shipped_entry_maps_to_the_espeak_form_it_declares() -> None:
    raw = yaml.safe_load(LEXICON_PATH.read_text("utf-8"))
    entries = {word: entry for word, entry in raw.items() if word != "version"}
    assert entries
    for word, entry in entries.items():
        assert to_espeak(entry["arpabet"].split()) == entry["espeak"].split(), word
        assert entry["why"], word


def test_load_lexicon_returns_arpabet_phones_by_word(tmp_path: Path) -> None:
    path = write(tmp_path, 'version: 1\n"tomato":\n  arpabet: T AH0 M EY1 T OW2\n')
    assert load_lexicon(path) == {"tomato": ["T", "AH0", "M", "EY1", "T", "OW2"]}


@pytest.mark.parametrize(
    "entry",
    [
        '"Tomato":\n  arpabet: T AH0 M EY1 T OW2\n',  # not normalised: upper case
        '"don’t":\n  arpabet: D OW1 N T\n',  # not normalised: curly apostrophe
        '"tomato":\n  arpabet: T AH0 M EY1 T OW9\n',  # not ARPAbet
        '"tomato":\n  arpabet: ""\n',  # empty
        '"tomato":\n  espeak: t ə m eɪ t oʊ\n',  # no arpabet
    ],
)
def test_a_bad_entry_is_rejected_when_the_file_loads(tmp_path: Path, entry: str) -> None:
    with pytest.raises(ValueError):
        load_lexicon(write(tmp_path, f"version: 1\n{entry}"))
