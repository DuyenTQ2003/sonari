"""The demo seed: the 13 passages the 20 practice sentences pin, so a fresh clone needs no crawl.

`tools/speaking_items/sources.jsonl` is a byte-for-byte copy of those lines of the trimmed corpus
(`make voa-trim`, rules `voa-trim/163aae96e072`). These checks run without a database: the file
passes the same validation `make ingest-sources` applies, and every item finds its sentence where
`make ingest-speaking-items` will look for it.
"""

from pathlib import Path

from sonari_core.content.ingest import load_passages
from sonari_core.content.speaking_ingest import load_items

TOOLS = Path(__file__).resolve().parents[3] / "tools" / "speaking_items"


def test_the_seed_is_a_valid_trimmed_corpus_of_exactly_the_pinned_passages() -> None:
    passages = load_passages(TOOLS / "sources.jsonl")
    items = load_items(TOOLS / "items.jsonl")
    assert {p.key for p in passages} == {item.source for item in items}
    assert len(passages) == 13
    assert len(items) == 20


def test_every_practice_sentence_is_in_its_seed_passage_unchanged() -> None:
    passages = {p.key: p for p in load_passages(TOOLS / "sources.jsonl")}
    for item in load_items(TOOLS / "items.jsonl"):
        line = passages[item.source].text[item.line]
        assert line[item.start : item.start + len(item.text)] == item.text, item.key
