import pytest
from voa_inventory.topics import _compile, load_topics


def test_all_eight_plan_units_are_present_in_order() -> None:
    topics = load_topics().topics
    assert [t.unit for t in topics] == list(range(1, 9))
    assert len({t.id for t in topics}) == 8


@pytest.mark.parametrize(
    ("keyword", "text", "hit"),
    [
        ("shop*", "Shoppers line up", True),
        ("shop*", "workshop", False),  # stems match word starts only
        ("son", "his son left", True),
        ("son", "season of sonnets", False),  # bare keywords are whole words
        ("day in the life", "A Day  in the Life of a nurse", True),
        ("art", "the art show", True),
        ("art", "smart phone", False),
    ],
)
def test_keyword_matching(keyword: str, text: str, hit: bool) -> None:
    assert bool(_compile(keyword).search(text.lower())) is hit


def test_a_title_hit_alone_tags_the_topic() -> None:
    tags = load_topics().tag("Restaurant Owners Struggle", "Officials spoke on Monday.")
    assert "food_restaurant" in tags


def test_one_paragraph_hit_is_not_enough_but_two_are() -> None:
    topics = load_topics()
    assert "shopping" not in topics.tag("Officials Meet", "Prices rose last week.")
    assert "shopping" in topics.tag("Officials Meet", "Prices rose as stores cut sales.")


def test_an_item_can_carry_several_topics() -> None:
    tags = load_topics().tag("Families Travel for the Holidays", "Trips by train and bus are up.")
    assert {"family_friends", "travel_transport"} <= set(tags)


def test_untagged_text_returns_nothing() -> None:
    assert load_topics().tag("Election Results", "Voters chose a new government.") == {}
