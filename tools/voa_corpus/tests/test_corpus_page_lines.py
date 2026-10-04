"""Two exact lines of VOA's lesson pages that are frame, each with the content it must not take."""

import pytest
from voa_corpus.boilerplate import classify


def removed(line: str) -> bool:
    hit = classify(line)
    return bool(hit) and hit[1] >= len(line.split())


HEADER = (
    "Read and listen to the article. Then open the activities on the right side of the page to "
    "improve your English!"
)


@pytest.mark.parametrize(
    "line",
    [
        HEADER,
        "Read and listen to the article.",
        "Then open the activities on the right side of the page to improve your English!",
        "(The story continues next week)",
    ],
)
def test_the_page_header_and_the_serial_note_are_frame(line: str) -> None:
    assert removed(line)


@pytest.mark.parametrize(
    "line",
    [
        "He likes to read and listen to the article on the radio every morning.",
        "Read and listen to the article. Then write what you think about the mayor.",
        "Then open the activities on the right side of the page.",
        "Open the activities on the right side of the page to improve your English!",
        "(The story continues in the next chapter.)",
        "(The story continues)",
        "The story continues next week, the editor said.",
        "The story continues next week with a new character.",
    ],
)
def test_the_nearest_content_is_kept(line: str) -> None:
    assert not removed(line)
