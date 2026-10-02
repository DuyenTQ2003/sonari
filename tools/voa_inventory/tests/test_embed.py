import numpy as np
import pytest
from voa_inventory.embed import EmbeddingTagger, assign
from voa_inventory.topics import TOPICS_PATH, Catalog, TopicMeta

KINDS = ["topic", "topic", "candidate", "other"]
IDS = ["food_restaurant", "shopping", "pets", "other_0"]


def test_assign_returns_the_nearest_topic_above_the_floor() -> None:
    tags = assign(np.array([0.7, 0.2, 0.3, 0.1]), KINDS, IDS, floor=0.4)
    assert tags.topics == {"food_restaurant": pytest.approx(0.7)}
    assert tags.candidates == {}


def test_assign_routes_a_candidate_to_candidates() -> None:
    tags = assign(np.array([0.2, 0.2, 0.6, 0.1]), KINDS, IDS, floor=0.4)
    assert tags.topics == {} and set(tags.candidates) == {"pets"}


def test_nearest_other_description_means_untagged_even_above_the_floor() -> None:
    assert assign(np.array([0.5, 0.2, 0.3, 0.8]), KINDS, IDS, floor=0.4) == assign(
        np.zeros(4), KINDS, IDS, floor=0.4
    )


def test_below_the_floor_means_untagged() -> None:
    tags = assign(np.array([0.39, 0.2, 0.3, 0.1]), KINDS, IDS, floor=0.4)
    assert tags.topics == {} and tags.candidates == {}


AXES = ["food", "shop", "pet", "politic"]


def fake_encode(texts):
    vectors = []
    for text in texts:
        # four topic axes plus twelve weak "generic" dimensions shared by every text
        v = np.array([float(axis in text.lower()) for axis in AXES] + [0.05] * 12)
        vectors.append(v / np.linalg.norm(v))
    return np.array(vectors, dtype=np.float32)


def fake_tagger() -> EmbeddingTagger:
    catalog = Catalog(
        topics=(
            TopicMeta("food_restaurant", 4, "Food", "food"),
            TopicMeta("shopping", 8, "Shopping", "shop"),
        ),
        candidates=(TopicMeta("pets", 0, "Pets", "pet"),),
        other=("politics",),
    )
    return EmbeddingTagger(TOPICS_PATH, encode=fake_encode, catalog=catalog)


def test_embedding_tagger_tags_end_to_end_with_a_fake_encoder() -> None:
    tagger = fake_tagger()
    tags = tagger.tag_all(
        [
            ("Best food in town", "a menu"),
            ("Shop until you drop", "sale"),
            ("A pet story", "dogs"),
            ("Politics today", "election"),
            ("Nothing relevant", "zzz"),
        ]
    )
    assert set(tags[0].topics) == {"food_restaurant"}
    assert set(tags[1].topics) == {"shopping"}
    assert set(tags[2].candidates) == {"pets"}
    assert tags[3].topics == {} and tags[3].candidates == {}
    assert tags[4].topics == {} and tags[4].candidates == {}
    assert tagger.tag_all([]) == []
    assert tagger.tags_only_usable
