"""Each word keeps the better of its en-us and en-gb scores."""

from tests.scoring.fakes import fake_pronouncer, posteriors

from sonari_speech.scoring.accents import score_accents
from sonari_speech.scoring.gop import Thresholds, load_vocab, score_words

T = Thresholds("test", 0.0, -3.0)


def frames_for(tokens: list[str]) -> list[str | None]:
    return [x for t in tokens for x in (None, t)] + [None]


def test_a_british_reading_is_scored_against_the_british_form() -> None:
    vocab = load_vocab()
    words = fake_pronouncer().pronounce("one you")  # en-us: w ʌ n | j uː
    log_probs = posteriors(vocab, frames_for(["w", "ɒ", "n", "j", "uː"]))
    american = score_words(words, log_probs, 0.0, T, vocab)
    assert american[0].verdict == "wrong"

    scored = score_accents(words, [("w", "ɒ", "n"), None], log_probs, 0.0, T, vocab)
    assert [(w.reference, w.verdict) for w in scored] == [
        ("en-gb", "correct"),
        ("en-us", "correct"),
    ]
    assert [p.expected for p in scored[0].phonemes] == ["w", "ɒ", "n"]


def test_an_american_reading_keeps_the_american_form() -> None:
    vocab = load_vocab()
    words = fake_pronouncer().pronounce("one you")
    log_probs = posteriors(vocab, frames_for(["w", "ʌ", "n", "j", "uː"]))
    scored = score_accents(words, [("w", "ɒ", "n"), None], log_probs, 0.0, T, vocab)
    assert [(w.reference, w.verdict) for w in scored] == [
        ("en-us", "correct"),
        ("en-us", "correct"),
    ]


def test_a_british_form_equal_to_the_american_one_is_not_scored_twice() -> None:
    vocab = load_vocab()
    words = fake_pronouncer().pronounce("you")
    log_probs = posteriors(vocab, frames_for(["j", "uː"]))
    same = score_accents(words, [("j", "uː")], log_probs, 0.0, T, vocab)
    assert same == score_words(words, log_probs, 0.0, T, vocab)


def test_a_british_sentence_too_long_for_the_frames_falls_back_to_en_us() -> None:
    vocab = load_vocab()
    words = fake_pronouncer().pronounce("you")
    log_probs = posteriors(vocab, ["j", "uː"])  # two frames: room for exactly two tokens
    scored = score_accents(words, [("j", "uː", "w")], log_probs, 0.0, T, vocab)
    assert scored[0].reference == "en-us"
