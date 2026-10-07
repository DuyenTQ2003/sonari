"""What kind of text a trimmed VOA passage is, and whether its topic needs a flag.

Measurement only (docs/reports/voa-classify.md): no LLM, nothing written, no threshold of the
level 4 filter touched. The type comes from the programme, the title and the structure of the
lines, in the fixed order of `classify_type`, and says which rule decided. The safety flags come
from the stems in `safety.tsv`. Both are leads for a reader, not a filter.
"""

import re
from pathlib import Path

TYPES = (
    "explainer", "news_item", "magazine", "english_teaching", "dialogue_script", "newscast",
    "fiction", "advice_column",
)  # fmt: skip
USABLE_TYPES = ("explainer", "news_item")  # a text about one thing that a lesson can be built on
BODY_HITS = 3  # a safety stem seen this often in the body is a theme, not a passing mention
# A disaster is flagged when it is reported with casualties, not when a phenomenon is explained:
# two outcome words in the past tense ("killed", "missing"), not an average ("tornadoes kill 70").
CASUALTIES = re.compile(
    r"\b(killed|killing|died|dead|death toll|missing|victims?|drowned|survivors?|bodies"
    r"|wounded|injured)\b",
    re.I,
)
CASUALTY_HITS = 2
WRITTEN_LESSONS = ("Words and Their Stories", "Everyday Grammar", "Ask a Teacher", "Early Literacy")
TEACHING = (*WRITTEN_LESSONS, "Let's Learn English")  # programmes about English itself
NEWS_PROGRAMMES = ("As It Is", "What's Trending Today?")  # news items, so a lower attribution bar
EDUCATION = ("Education", "Education Tips")
SAFETY = {
    cat: re.compile(rf"\b(?:{stems})", re.I)
    for cat, stems in (
        line.split("\t")
        for line in Path(__file__).with_name("safety.tsv").read_text("utf-8").splitlines()
        if line and not line.startswith("#")
    )
}

WORD = re.compile(r"[A-Za-z']+")
ATTRIBUTION = re.compile(
    r"\b(said|says|told|according to|reported|announced|added|noted|officials?)\b", re.I
)
SECOND_PERSON = re.compile(r"\b(you|your|yours)\b", re.I)
SPEAKER = re.compile(r"^[A-Z][A-Za-z.' ]{0,30}:\s+\S")
HEADING = re.compile(r"^[^.?!”\"]{2,70}[^.?!”\":;,]$")  # a short line with no closing punctuation
TEACHING_TITLE = re.compile(
    r"^\s*(Words and Their Stories|Ask a Teacher|Everyday Grammar|English Through Music"
    r"|Let.s Learn English"
    r"|Lesson #?\d+)\b", re.I,
)  # fmt: skip
ENGLISH_TIP = re.compile(
    r"english|pronunciation|vocabulary|grammar|speaking|language|learner", re.I
)


def features(lines: list[str]) -> dict[str, float]:
    """Word densities per 100 words, speaker-labelled lines, and short headings."""
    text = " ".join(lines)
    n = max(len(WORD.findall(text)), 1)
    speakers = sum(bool(SPEAKER.match(x)) for x in lines)

    def per100(rx: re.Pattern[str]) -> float:
        return 100 * len(rx.findall(text)) / n

    return {
        "attribution": per100(ATTRIBUTION),
        "second_person": per100(SECOND_PERSON),
        "speakers": speakers,
        "speaker_share": speakers / max(len(lines), 1),
        "headings": sum(bool(HEADING.match(x.strip())) and len(x.split()) <= 9 for x in lines),
    }


def classify_type(title: str, program: str, lines: list[str]) -> tuple[str, str]:
    """(type, the rule that decided it). The first rule that fits wins."""
    f = features(lines)
    title = title.strip()
    if re.match(r"VOA (Special )?English Newscast", title):
        return "newscast", "title: newscast"
    if re.match(r"(Man|Woman|Boy|Girl), \d+, ", title):
        return "advice_column", "title: reader letter"
    if f["speakers"] >= 6 and f["speaker_share"] >= 0.5 and not program.startswith(WRITTEN_LESSONS):
        return "dialogue_script", "lines: speaker labels"
    if program.startswith("American Stories") or re.search(r"\bPresents '", title):
        return "fiction", "programme or title: story"
    if program.startswith(TEACHING) or TEACHING_TITLE.match(title):
        return "english_teaching", "programme or title: English lesson"
    if program in EDUCATION and ENGLISH_TIP.search(title):
        return "english_teaching", "education programme, title about English"
    if any(re.match(r"LESSON \d+", x) for x in lines[:3]):
        return "english_teaching", "lines: lesson header"
    if title.startswith("American Mosaic") or title.count(";") >= 2:
        return "magazine", "title: several segments"
    bar = 0.25 if program in NEWS_PROGRAMMES else 0.5
    if f["attribution"] >= bar and f["second_person"] < 1.5 and f["headings"] < 3:
        return "news_item", "lines: reported speech"
    return "explainer", "default"


def safety_hits(title: str, lead: str, lines: list[str]) -> dict[str, tuple[bool, int]]:
    """Per category: does a stem occur in the title or lead, and how often in the body."""
    head, body = f"{title} {lead}", " ".join(lines)
    hits = {c: (bool(rx.search(head)), len(rx.findall(body))) for c, rx in SAFETY.items()}
    if len(CASUALTIES.findall(body)) < CASUALTY_HITS:
        hits["disaster"] = (False, 0)  # a tornado explained, or a flood with nobody hurt
    return hits


def safety_flags(hits: dict[str, tuple[bool, int]], body_hits: int = BODY_HITS) -> frozenset[str]:
    """The categories a reader should look at: a hit in the title or lead, or a recurring theme."""
    return frozenset(c for c, (in_head, n) in hits.items() if in_head or n >= body_hits)
