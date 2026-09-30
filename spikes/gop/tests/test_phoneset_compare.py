from phoneset.compare import (
    diff_ops,
    explaining_folds,
    fold,
    fold_flap,
    fold_reduced,
    fold_syllabic,
    strip_stress,
)


def test_strip_stress_handles_glued_and_free_marks() -> None:
    assert strip_stress(["θ", "ˈɪ", "ŋ", "ˌ", "k"]) == ["θ", "ɪ", "ŋ", "k"]


def test_fold_syllabic_splits_and_treats_glottal_stop_as_t() -> None:
    assert fold_syllabic(["l", "ɪ", "ɾ", "əl"]) == ["l", "ɪ", "ɾ", "ə", "l"]
    assert fold_syllabic(["b", "ʌ", "ʔ", "n̩"]) == ["b", "ʌ", "t", "ə", "n"]


def test_fold_reduced_merges_only_the_reduced_class() -> None:
    assert fold_reduced(["ᵻ", "ɐ", "ɪ", "ə", "ɛ", "ʌ"]) == ["ə", "ə", "ə", "ə", "ɛ", "ʌ"]


def test_fold_flap_needs_a_vowel_on_both_sides() -> None:
    assert fold_flap(["w", "ɔː", "t", "ɚ"]) == ["w", "ɔː", "ɾ", "ɚ"]
    assert fold_flap(["s", "ɪ", "d", "i"]) == ["s", "ɪ", "ɾ", "i"]
    assert fold_flap(["t", "ɪ", "n"]) == ["t", "ɪ", "n"]
    assert fold_flap(["ɪ", "t", "s"]) == ["ɪ", "t", "s"]


def test_flap_fold_does_not_hide_a_real_consonant_difference() -> None:
    assert fold(["b", "ɪ", "k", "ɚ"]) != fold(["b", "ɪ", "t", "ɚ"])
    assert fold(["s", "ɪ", "n"]) != fold(["s", "ɪ", "ŋ"])


def test_explaining_folds_names_the_rules_that_helped() -> None:
    mapped = ["l", "ɪ", "t", "ə", "l"]
    espeak = ["l", "ɪ", "ɾ", "əl"]
    assert explaining_folds(mapped, espeak) == ["syllabic/glottal", "flap"]
    assert explaining_folds(["f", "æ", "m", "ə", "l", "i"], ["f", "æ", "m", "ɪ", "l", "i"]) == [
        "reduced vowel"
    ]
    assert explaining_folds(["k", "ɪ", "t"], ["k", "ɛ", "t"]) == []


def test_diff_ops_lists_only_the_differing_spans() -> None:
    assert diff_ops(["k", "ɑː", "t"], ["k", "ɔ", "t"]) == [("ɑː", "ɔ")]
    assert diff_ops(["a", "b"], ["a", "b"]) == []
