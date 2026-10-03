import pytest

from sonari_speech.g2p.contractions import attach_clitic, split_clitic


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("couldn't", ("could", "n't")),
        ("mustn't", ("must", "n't")),
        ("anna's", ("anna", "'s")),
        ("they'd", ("they", "'d")),
        ("we'll", ("we", "'ll")),
        ("you're", ("you", "'re")),
        ("should've", ("should", "'ve")),
        ("i'm", ("i", "'m")),
    ],
)
def test_split_clitic(word: str, expected: tuple[str, str]) -> None:
    assert split_clitic(word) == expected


@pytest.mark.parametrize("word", ["o'clock", "rock'n'roll", "dog", "'s", "n't", "t's"])
def test_words_that_are_not_stem_plus_clitic_do_not_split(word: str) -> None:
    assert split_clitic(word) is None


def phones(text: str) -> list[str]:
    return text.split()


@pytest.mark.parametrize(
    ("stem", "clitic", "expected"),
    [
        # n't: a syllabic n after a consonant, a bare n t after a vowel.
        ("M AH1 S T", "n't", "M AH1 S T AH0 N T"),
        ("SH UH1 D", "n't", "SH UH1 D AH0 N T"),
        ("M EY1", "n't", "M EY1 N T"),
        # 's agrees in voicing with the stem: s after voiceless, iz after a sibilant, z else.
        ("K AE1 T", "'s", "K AE1 T S"),
        ("B AO1 S", "'s", "B AO1 S IH0 Z"),
        ("CH ER1 CH", "'s", "CH ER1 CH IH0 Z"),
        ("AE1 N AH0", "'s", "AE1 N AH0 Z"),
        ("D AO1 G", "'s", "D AO1 G Z"),
        # 'll, 've, 'd: a schwa after a consonant, none after a vowel.
        ("T AA1 M", "'ll", "T AA1 M AH0 L"),
        ("D AA1 K T ER0", "'ll", "D AA1 K T ER0 L"),  # ER is a vowel
        ("SH IY1", "'ll", "SH IY1 L"),
        ("K UH1 D", "'ve", "K UH1 D AH0 V"),
        ("AY1", "'ve", "AY1 V"),
        ("DH EY1", "'d", "DH EY1 D"),
        ("T AA1 M", "'d", "T AA1 M AH0 D"),
        ("AY1", "'m", "AY1 M"),
        ("Y UW1", "'re", "Y UW1 ER0"),
    ],
)
def test_attach_clitic(stem: str, clitic: str, expected: str) -> None:
    assert attach_clitic(phones(stem), clitic) == phones(expected)


def test_attach_clitic_rejects_an_unknown_clitic() -> None:
    with pytest.raises(ValueError):
        attach_clitic(["K", "AE1", "T"], "'z")
