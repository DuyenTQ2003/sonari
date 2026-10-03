import pytest

from sonari_speech.phoneset.mapping import load_table, mapped_tokens, split_stress, to_espeak

ARPABET_PHONES = [
    *("AA", "AE", "AH", "AO", "AW", "AY", "B", "CH", "D", "DH", "EH", "ER", "EY", "F", "G"),
    *("HH", "IH", "IY", "JH", "K", "L", "M", "N", "NG", "OW", "OY", "P", "R", "S", "SH", "T"),
    *("TH", "UH", "UW", "V", "W", "Y", "Z", "ZH"),
]


def test_table_has_one_entry_per_arpabet_phone() -> None:
    assert sorted(load_table()["phones"]) == sorted(ARPABET_PHONES)
    assert len(ARPABET_PHONES) == 39


def test_g_is_the_script_g_of_the_vocab_not_ascii_g() -> None:
    assert to_espeak(["G"]) == ["ɡ"]
    assert "g" not in mapped_tokens()


@pytest.mark.parametrize(
    ("phones", "expected"),
    [
        # The hand-written tokens of the P02 spike.
        ("TH IH1 NG K", "θ ɪ ŋ k"),
        ("TH R IY1", "θ ɹ iː"),
        ("TH AE1 NG K", "θ æ ŋ k"),
        ("TH AO1 T", "θ ɔː t"),
        ("T IH1 N", "t ɪ n"),
        ("T UH1 K", "t ʊ k"),
        ("T AO1 K", "t ɔː k"),
        ("T AY1 M", "t aɪ m"),
        # Affricates and diphthongs are single vocab tokens.
        ("CH OY1 S", "tʃ ɔɪ s"),
        ("JH OW1", "dʒ oʊ"),
    ],
)
def test_words_map_to_espeak_tokens(phones: str, expected: str) -> None:
    assert to_espeak(phones.split()) == expected.split()


def test_stress_digits_are_stripped_and_schwa_follows_stress_zero() -> None:
    assert to_espeak(["AH1"]) == ["ʌ"]
    assert to_espeak(["AH2"]) == ["ʌ"]
    assert to_espeak(["AH0"]) == ["ə"]
    assert to_espeak(["ER1"]) == ["ɜː"]
    assert to_espeak(["ER0"]) == ["ɚ"]
    assert to_espeak(["IH0"]) == ["ɪ"]


@pytest.mark.parametrize(
    ("phones", "expected"),
    [
        ("K AA1 R", "k ɑːɹ"),  # one token before the word end ...
        ("P AA1 R T", "p ɑːɹ t"),  # ... and before a consonant
        ("F AO1 R", "f ɔːɹ"),
        ("K EH1 R", "k ɛɹ"),
        ("N IH1 R", "n ɪɹ"),
        ("HH IY1 R", "h ɪɹ"),  # CMUdict spells the NEAR set with IY
        ("P UH1 R", "p ʊɹ"),
        ("V EH1 R IY0", "v ɛ ɹ i"),  # before a vowel EH and R stay apart
        ("S AA1 R IY0", "s ɑː ɹ i"),
        ("D UH1 R IH0 NG", "d ʊɹ ɹ ɪ ŋ"),  # espeak doubles the r after UH
        ("F AY1 ER0", "f aɪɚ"),
        ("R IH0 T AY1 R", "ɹ ɪ t aɪɚ"),
        ("V AY1 R AH0 S", "v aɪ ɹ ə s"),
        ("S AY1 AH0 N S", "s aɪə n s"),
        ("EH1 R IY0 AH0", "ɛ ɹ iə"),
    ],
)
def test_r_coloured_vowels_and_vowel_merges(phones: str, expected: str) -> None:
    assert to_espeak(phones.split()) == expected.split()


@pytest.mark.parametrize(
    ("phones", "expected"),
    [
        ("HH AE1 P IY0", "h æ p i"),  # word-final
        ("K R IY0 EY1 T", "k ɹ iː eɪ t"),  # before a vowel
        ("EH1 N IY0 TH IH2 NG", "ɛ n ɪ θ ɪ ŋ"),  # before a consonant
        ("F IY1 L", "f iː l"),  # stressed IY is always long
    ],
)
def test_unstressed_iy_depends_on_position(phones: str, expected: str) -> None:
    assert to_espeak(phones.split()) == expected.split()


def test_er_before_a_vowel_is_followed_by_r() -> None:
    assert to_espeak(["ER0", "AW1", "N", "D"]) == ["ɚ", "ɹ", "aʊ", "n", "d"]
    assert to_espeak(["K", "ER1", "AH0", "N", "T"]) == ["k", "ɜː", "ɹ", "ə", "n", "t"]
    assert to_espeak(["T", "IY1", "CH", "ER0"]) == ["t", "iː", "tʃ", "ɚ"]


def test_split_stress() -> None:
    assert split_stress("IH1") == ("IH", 1)
    assert split_stress("TH") == ("TH", None)


@pytest.mark.parametrize("bad", ["", "th", "IH3", "X1", " ", "?"])
def test_non_arpabet_input_is_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        to_espeak([bad])
