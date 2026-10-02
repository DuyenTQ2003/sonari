from pathlib import Path

import pytest
from voa_inventory.evaluate import Cell, choose, f_beta, load_labels, pooled, render, score, wilson
from voa_inventory.topics import load_catalog

IDS = ["food_restaurant", "shopping"]
LABELS = {
    "u1": "food_restaurant",
    "u2": "food_restaurant",
    "u3": "shopping",
    "u4": "none",
    "u5": "none",
}


def test_score_counts_true_and_false_positives_and_misses() -> None:
    predicted = {
        "u1": {"food_restaurant"},  # correct
        "u2": set(),  # missed
        "u3": {"food_restaurant", "shopping"},  # shopping correct, food wrong
        "u4": {"food_restaurant"},  # wrong on a `none` page
        "u5": set(),
    }
    cells = score(predicted, LABELS, IDS)
    assert cells["food_restaurant"] == Cell(tp=1, fp=2, fn=1)
    assert cells["shopping"] == Cell(tp=1, fp=0, fn=0)
    assert cells["food_restaurant"].precision == pytest.approx(1 / 3)
    assert cells["food_restaurant"].recall == pytest.approx(1 / 2)
    assert pooled(cells) == Cell(tp=2, fp=2, fn=1)


def test_precision_and_recall_are_undefined_without_data() -> None:
    assert Cell().precision is None and Cell().recall is None
    assert f_beta(Cell()) == 0.0


def test_f_beta_weights_precision_more_than_recall() -> None:
    high_precision = Cell(tp=5, fp=0, fn=5)  # P 1.0, R 0.5
    high_recall = Cell(tp=5, fp=5, fn=0)  # P 0.5, R 1.0
    assert f_beta(high_precision) > f_beta(high_recall)
    assert f_beta(Cell(tp=4, fp=0, fn=0)) == pytest.approx(1.0)


def test_wilson_interval_brackets_the_rate_and_widens_with_less_data() -> None:
    lo, hi = wilson(3, 10)
    assert lo < 0.3 < hi
    lo_small, hi_small = wilson(1, 3)
    assert hi_small - lo_small > hi - lo
    assert wilson(0, 0) == (0.0, 1.0)


def test_choose_prefers_the_phrase_tagger_unless_embedding_is_clearly_better() -> None:
    phrase = {"a": Cell(tp=6, fp=4, fn=4)}
    slightly_better = {"a": Cell(tp=6, fp=4, fn=3)}
    much_better = {"a": Cell(tp=9, fp=1, fn=1)}
    assert choose(phrase, slightly_better) == "phrase"  # within the tie band
    assert choose(phrase, much_better) == "embedding"
    assert choose(much_better, phrase) == "phrase"


def write(path: Path, rows: list[tuple[str, str]]) -> Path:
    path.write_text(
        "n,url,title,label\n" + "".join(f"{i},{u},T,{lab}\n" for i, (u, lab) in enumerate(rows, 1)),
        encoding="utf-8",
    )
    return path


def test_load_labels_accepts_topics_candidates_and_none(tmp_path: Path) -> None:
    valid = {"shopping", "pets"}
    path = write(tmp_path / "l.csv", [("u1", "shopping"), ("u2", "none"), ("u3", "pets")])
    assert load_labels(path, valid) == {"u1": "shopping", "u2": "none", "u3": "pets"}


@pytest.mark.parametrize("bad", ["", "shoping", "None ", "food"])
def test_load_labels_rejects_blank_or_unknown_labels(tmp_path: Path, bad: str) -> None:
    path = write(tmp_path / "l.csv", [("u1", "shopping"), ("u2", bad)])
    with pytest.raises(ValueError, match="row 2"):
        load_labels(path, {"shopping"})


def test_render_states_the_choice_the_counts_and_that_old_counts_were_upper_bounds() -> None:
    catalog = load_catalog()
    ids = [t.id for t in catalog.topics]
    cids = [c.id for c in catalog.candidates]
    labels = {f"u{i}": "none" for i in range(4)} | {"u9": "food_restaurant"}
    predicted_old = {u: {"food_restaurant"} for u in labels}  # tags everything
    predicted_new = {u: ({"food_restaurant"} if u == "u9" else set()) for u in labels}
    results = {
        "keyword-v1": score(predicted_old, labels, ids),
        "phrase": score(predicted_new, labels, ids),
    }
    cresults = {n: score({u: set() for u in labels}, labels, cids) for n in results}
    text = render(results, cresults, labels, catalog, "phrase")
    assert "**Chosen: `phrase`.**" in text
    assert "The earlier counts were upper bounds." in text
    assert "1 of 5 were correct" in text  # the baseline tagged 5 pages, 1 correctly
    assert "1.00 (1/1)" in text  # the new tagger's precision on food, with counts
