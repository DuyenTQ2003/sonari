"""Topic tagging of inventory items: phrase matching with stop patterns.

`topics.yaml` (current) uses topic-specific phrases plus negative patterns. The previous
approach, bare keywords with no stop patterns, lives on as `topics_v1.yaml` so that it can
be measured against the same labelled set. Both files share one format and one matcher.

Every tagger exposes `tag_all(pairs) -> list[Tags]` for (title, first paragraph) pairs.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml

TOPICS_PATH = Path(__file__).with_name("topics.yaml")
V1_PATH = Path(__file__).with_name("topics_v1.yaml")


@dataclass(frozen=True)
class TopicMeta:
    id: str
    unit: int
    label: str
    description: str


@dataclass(frozen=True)
class Catalog:
    """What exists, independent of how an item is matched to it."""

    topics: tuple[TopicMeta, ...]
    candidates: tuple[TopicMeta, ...]
    other: tuple[str, ...]  # descriptions of off-topic content (embedding tagger only)


@dataclass(frozen=True)
class Tags:
    topics: dict[str, float] = field(default_factory=dict)
    candidates: dict[str, float] = field(default_factory=dict)


def _compile(pattern: str) -> re.Pattern[str]:
    """A word or phrase, whole-word; a trailing `*` also matches longer words."""
    stem = pattern.endswith("*")
    body = re.escape(pattern.rstrip("*").lower()).replace(r"\ ", r"\s+")
    return re.compile(rf"\b{body}" + (r"\w*\b" if stem else r"\b"))


@dataclass(frozen=True)
class Topic:
    id: str
    patterns: tuple[re.Pattern[str], ...]
    stop: tuple[re.Pattern[str], ...]


def _blank(text: str, stops: Sequence[re.Pattern[str]]) -> str:
    for rx in stops:
        text = rx.sub(" ", text)
    return text


@dataclass(frozen=True)
class TopicSet:
    topics: tuple[Topic, ...]
    min_score: int
    title_weight: int
    global_stop: tuple[re.Pattern[str], ...] = ()

    def tag(self, title: str, first_paragraph: str) -> dict[str, float]:
        """Topic id -> score, for every topic whose score reaches min_score.

        Stop patterns are blanked out of the text first, so "White House" cannot supply the
        word "house" to a housing topic. Each distinct phrase in the title scores
        `title_weight`, each distinct phrase in the first paragraph scores 1.
        """
        title, para = (
            _blank(title.lower(), self.global_stop),
            _blank(first_paragraph.lower(), self.global_stop),
        )
        scores: dict[str, float] = {}
        for topic in self.topics:
            t, p = _blank(title, topic.stop), _blank(para, topic.stop)
            score = sum(
                self.title_weight * bool(rx.search(t)) + bool(rx.search(p)) for rx in topic.patterns
            )
            if score >= self.min_score:
                scores[topic.id] = float(score)
        return scores


def _read(path: Path) -> dict:
    return yaml.safe_load(path.read_text("utf-8"))


def _meta(data: dict, group: str) -> tuple[TopicMeta, ...]:
    return tuple(
        TopicMeta(tid, spec.get("unit", 0), spec["label"], spec.get("description", "").strip())
        for tid, spec in data.get(group, {}).items()
    )


def load_catalog(path: Path = TOPICS_PATH) -> Catalog:
    data = _read(path)
    return Catalog(_meta(data, "topics"), _meta(data, "candidates"), tuple(data.get("other", ())))


def _topic_set(data: dict, group: str) -> TopicSet:
    topics = tuple(
        Topic(
            tid,
            tuple(_compile(p) for p in spec.get("phrases", spec.get("keywords", []))),
            tuple(_compile(p) for p in spec.get("stop", [])),
        )
        for tid, spec in data.get(group, {}).items()
    )
    stop = tuple(_compile(p) for p in data.get("stop", []))
    return TopicSet(topics, data["min_score"], data["title_weight"], stop)


def load_topics(path: Path = TOPICS_PATH) -> TopicSet:
    """The eight level 4 candidate topics of PLAN-v7 4.1."""
    return _topic_set(_read(path), "topics")


def load_candidates(path: Path = TOPICS_PATH) -> TopicSet:
    """Replacement topics, matched with the same rules."""
    return _topic_set(_read(path), "candidates")


class PhraseTagger:
    """Phrase matching with stop patterns. With `topics_v1.yaml` it is the old keyword tagger."""

    tags_only_usable = False

    def __init__(self, path: Path = TOPICS_PATH, name: str = "phrase") -> None:
        self.name = name
        self._topics, self._candidates = load_topics(path), load_candidates(path)

    def tag_all(self, pairs: Sequence[tuple[str, str]]) -> list[Tags]:
        return [Tags(self._topics.tag(t, p), self._candidates.tag(t, p)) for t, p in pairs]


def keyword_tagger() -> PhraseTagger:
    """The pre-fix tagger (bare keywords, no stop patterns), kept as the baseline."""
    return PhraseTagger(V1_PATH, "keyword-v1")
