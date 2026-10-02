import pytest
from voa_inventory.topics import PhraseTagger, _compile, keyword_tagger, load_catalog


def plan(tagger: PhraseTagger, title: str, para: str = "") -> set[str]:
    return set(tagger.tag_all([(title, para)])[0].topics)


def candidates(tagger: PhraseTagger, title: str, para: str = "") -> set[str]:
    return set(tagger.tag_all([(title, para)])[0].candidates)


def test_all_eight_plan_units_and_the_candidates_are_in_the_catalog() -> None:
    catalog = load_catalog()
    assert [t.unit for t in catalog.topics] == list(range(1, 9))
    assert len({t.id for t in catalog.topics}) == 8
    assert all(t.description for t in [*catalog.topics, *catalog.candidates])
    assert len(catalog.other) >= 5


@pytest.mark.parametrize(
    ("keyword", "text", "hit"),
    [
        ("shop*", "Shoppers line up", True),
        ("shop*", "workshop", False),  # stems match word starts only
        ("son", "his son left", True),
        ("son", "season of sonnets", False),  # bare words are whole words
        ("day in the life", "A Day  in the Life of a nurse", True),
        ("art", "the art show", True),
        ("art", "smart phone", False),
        ("oil-for-food", "the oil-for-food scandal", True),
    ],
)
def test_pattern_matching(keyword: str, text: str, hit: bool) -> None:
    assert bool(_compile(keyword).search(text.lower())) is hit


def test_a_title_hit_alone_tags_the_topic() -> None:
    assert "food_restaurant" in plan(PhraseTagger(), "Chefs Open a New Restaurant")


def test_one_paragraph_hit_is_not_enough_but_two_are() -> None:
    tagger = PhraseTagger()
    assert "shopping" not in plan(tagger, "Officials Meet", "Shoppers gathered on Monday.")
    assert "shopping" in plan(tagger, "Officials Meet", "Shoppers found deep discounts.")


def test_an_item_can_carry_several_topics() -> None:
    tags = plan(PhraseTagger(), "Families Travel for the Holidays", "Trips by train are up.")
    assert {"family_friends", "travel_transport"} <= tags


def test_untagged_text_returns_nothing() -> None:
    assert plan(PhraseTagger(), "Election Results", "Voters chose a new government.") == set()


@pytest.mark.parametrize(
    "title",
    [
        "White House Weighs New Rules",
        "House Speaker Meets Leaders",
        "The Fall of the House of Usher",
        "Freedom House Reports on Elections",
        "Trending Today: 'Fuller House' Now on Netflix",
        "Building Boats Helps At-Risk Young Adults Improve Their Lives",
    ],
)
def test_house_and_building_titles_are_not_housing(title: str) -> None:
    assert "housing_home" not in candidates(PhraseTagger(), title)


def test_real_housing_stories_are_still_tagged() -> None:
    tagger = PhraseTagger()
    assert "housing_home" in candidates(tagger, "Landlords Raise Rent as Apartment Costs Climb")
    assert "housing_home" in candidates(tagger, "Man Builds His Dream House", "A tiny house.")


@pytest.mark.parametrize(
    "title",
    [
        "Sam Cooke Sang of Love and Loss",
        "The Oil-for-Food Scandal Reaches Court",
        "Food Aid Reaches Flooded Villages",
        "Food Security Worries Grow",
        "Cook County Votes on Budget",
    ],
)
def test_food_words_in_names_and_aid_stories_are_not_eating(title: str) -> None:
    assert "food_restaurant" not in plan(PhraseTagger(), title)


def test_real_food_stories_are_still_tagged() -> None:
    tagger = PhraseTagger()
    assert "food_restaurant" in plan(tagger, "Cooking at Home: Three Simple Recipes")
    assert "food_restaurant" in plan(tagger, "Street Food Vendors Return", "Fast food chains.")


def test_the_old_keyword_tagger_is_kept_as_the_measured_baseline() -> None:
    # The false positive that motivated the change: the bare word "house" tagged housing.
    old, new = keyword_tagger(), PhraseTagger()
    title = "White House Weighs New Rules"
    assert old.name == "keyword-v1" and "housing_home" in candidates(old, title)
    assert "housing_home" not in candidates(new, title)


def test_stop_patterns_do_not_hide_the_same_word_elsewhere_in_the_text() -> None:
    tags = candidates(PhraseTagger(), "White House Aide Rents Apartment", "A landlord said so.")
    assert "housing_home" in tags  # "rent", "apartment" and "landlord" survive
