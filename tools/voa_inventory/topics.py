"""Keyword tagging of inventory items with the level 4 candidate topics."""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

TOPICS_PATH = Path(__file__).with_name("topics.yaml")


@dataclass(frozen=True)
class Topic:
    id: str
    unit: int
    label: str
    patterns: tuple[tuple[str, re.Pattern[str]], ...]  # (keyword, compiled)


def _compile(keyword: str) -> re.Pattern[str]:
    stem = keyword.endswith("*")
    body = re.escape(keyword.rstrip("*").lower()).replace(r"\ ", r"\s+")
    return re.compile(rf"\b{body}" + (r"\w*\b" if stem else r"\b"))


@dataclass(frozen=True)
class TopicSet:
    topics: tuple[Topic, ...]
    min_score: int
    title_weight: int

    def tag(self, title: str, first_paragraph: str) -> dict[str, int]:
        """Topic id -> score, for every topic whose score reaches min_score."""
        title, para = title.lower(), first_paragraph.lower()
        scores = {}
        for topic in self.topics:
            score = sum(
                self.title_weight * bool(rx.search(title)) + bool(rx.search(para))
                for _, rx in topic.patterns
            )
            if score >= self.min_score:
                scores[topic.id] = score
        return scores


def _topic_set(data: dict, group: str) -> TopicSet:
    topics = tuple(
        Topic(
            id=tid,
            unit=spec.get("unit", 0),
            label=spec["label"],
            patterns=tuple((kw, _compile(kw)) for kw in spec["keywords"]),
        )
        for tid, spec in data[group].items()
    )
    return TopicSet(topics, data["min_score"], data["title_weight"])


def load_topics(path: Path = TOPICS_PATH) -> TopicSet:
    """The eight level 4 candidate topics of PLAN-v7 4.1."""
    return _topic_set(yaml.safe_load(path.read_text("utf-8")), "topics")


def load_candidates(path: Path = TOPICS_PATH) -> TopicSet:
    """Replacement topics, scored with the same rules."""
    return _topic_set(yaml.safe_load(path.read_text("utf-8")), "candidates")
