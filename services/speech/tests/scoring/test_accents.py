"""Each word keeps the best of its en-us, en-gb and weak-form scores."""

from tests.scoring.fakes import fake_pronouncer, posteriors

from sonari_speech.scoring.accents import score_accents
from sonari_speech.scoring.gop import Thresholds, load_vocab, score_words

T = Thresholds("test", 0.0, -3.0)
GB = ("en-gb", [("w", "ɒ", "n"), None])  # "one" in en-gb; "you" has no other form


def frames_for(tokens: list[str]) -> list[str | None]:
    return [x for t in tokens for x in (None, t)] + [None]


def test_a_british_reading_is_scored_against_the_british_form() -> None:
    vocab = load_vocab()
    words = fake_pronouncer().pronounce("one you")  # en-us: w ʌ n | j uː
    log_probs = posteriors(vocab, frames_for(["w", "ɒ", "n", "j", "uː"]))
    american = score_words(words, log_probs, 0.0, T, vocab)
    assert american[0].verdict == "wrong"

    scored = score_accents(words, [GB], log_probs, 0.0, T, vocab)
    assert [(w.reference, w.verdict) for w in scored] == [
        ("en-gb", "correct"),
        ("en-us", "correct"),
    ]
    assert [p.expected for p in scored[0].phonemes] == ["w", "ɒ", "n"]


def test_an_american_reading_keeps_the_american_form() -> None:
    vocab = load_vocab()
    words = fake_pronouncer().pronounce("one you")
    log_probs = posteriors(vocab, frames_for(["w", "ʌ", "n", "j", "uː"]))
    scored = score_accents(words, [GB], log_probs, 0.0, T, vocab)
    assert [(w.reference, w.verdict) for w in scored] == [
        ("en-us", "correct"),
        ("en-us", "correct"),
    ]


def test_a_form_equal_to_the_american_one_is_not_scored_twice() -> None:
    vocab = load_vocab()
    words = fake_pronouncer().pronounce("you")
    log_probs = posteriors(vocab, frames_for(["j", "uː"]))
    same = score_accents(words, [("en-gb", [("j", "uː")])], log_probs, 0.0, T, vocab)
    assert same == score_words(words, log_probs, 0.0, T, vocab)


def test_a_british_sentence_too_long_for_the_frames_falls_back_to_en_us() -> None:
    vocab = load_vocab()
    words = fake_pronouncer().pronounce("you")
    log_probs = posteriors(vocab, ["j", "uː"])  # two frames: room for exactly two tokens
    scored = score_accents(words, [("en-gb", [("j", "uː", "w")])], log_probs, 0.0, T, vocab)
    assert scored[0].reference == "en-us"


def test_a_weak_form_that_fits_better_is_kept_and_stays_en_us() -> None:
    vocab = load_vocab()
    words = fake_pronouncer().pronounce("one you")  # "you": j uː; the speaker says j ə
    log_probs = posteriors(vocab, frames_for(["w", "ʌ", "n", "j", "ə"]))
    weak = ("en-us", [None, ("j", "ə")])
    scored = score_accents(words, [GB, weak], log_probs, 0.0, T, vocab)
    assert [(w.reference, w.verdict) for w in scored] == [("en-us", "correct")] * 2
    assert [p.expected for p in scored[1].phonemes] == ["j", "ə"]
    assert scored[0] == score_words(words, log_probs, 0.0, T, vocab)[0]


def test_a_tie_keeps_the_earlier_reference() -> None:
    vocab = load_vocab()
    words = fake_pronouncer().pronounce("you")  # both readings fit the frames equally
    log_probs = posteriors(vocab, frames_for(["j", "uː"]))
    scored = score_accents(words, [("en-us", [("j", "ə")])], log_probs, 0.0, T, vocab)
    assert [p.expected for p in scored[0].phonemes] == ["j", "uː"]


def test_a_weak_form_cannot_hide_a_wrong_phoneme_it_does_not_cover() -> None:
    vocab = load_vocab()
    words = fake_pronouncer().pronounce("one you")  # the speaker says neither "you" form
    log_probs = posteriors(vocab, frames_for(["w", "ʌ", "n", "j", "s"]))
    weak = ("en-us", [None, ("j", "ə")])
    scored = score_accents(words, [GB, weak], log_probs, 0.0, T, vocab)
    assert scored[1].verdict == "wrong"
