import csv
from pathlib import Path

from voa_inventory.parse import Item
from voa_inventory.render import candidate_table, render_md, topic_table
from voa_inventory.rows import Row, count_usable, write_csv
from voa_inventory.topics import load_catalog


def item(
    n: int,
    *,
    license_ok: bool = True,
    has_audio: bool = True,
    words: int = 300,
    reasons: tuple[str, ...] = (),
) -> Item:
    return Item(
        url=f"https://example.test/a/{n}.html",
        title=f"Title {n}",
        program="As It Is",
        date="2025-01-01",
        byline="VOA Learning English",
        credit_line="",
        has_audio=has_audio,
        audio_url="x.mp3" if has_audio else "",
        word_count=words,
        avg_sentence_len=10.0,
        fk_grade=6.0,
        first_paragraph="",
        license_ok=license_ok,
        license_reasons=reasons,
    )


def row(n: int, level: int = 4, **kw) -> Row:
    return Row(item(n, **kw), level, {"food_restaurant": 3.0}, {"housing_home": 2.0})


def unusable_variants() -> list[Row]:
    """Rows that carry the same tags and level as a usable row but must never be counted."""
    return [
        row(10, license_ok=False, reasons=("byline_not_staff",)),
        row(11, license_ok=False, reasons=("wire_credit",)),
        row(12, has_audio=False),
        row(13, words=40),
    ]


def test_no_unusable_row_reaches_a_usable_count() -> None:
    rows = [row(1), *unusable_variants()]
    assert [r.usable for r in rows] == [True, False, False, False, False]
    for candidate in (False, True):
        topic = "housing_home" if candidate else "food_restaurant"
        counts, pool = count_usable(rows, topic, candidate)
        assert (counts.level4, counts.levels45, counts.any_level) == (1, 1, 1)
        assert [r.item.url for r in pool] == [rows[0].item.url]


def test_every_table_and_the_csv_agree_with_an_independent_recount(tmp_path: Path) -> None:
    rows = [row(1), row(2, level=5), row(3, level=7), *unusable_variants()]
    catalog = load_catalog()
    topics, _ = topic_table(rows, catalog, coverage=1.0)
    cands = candidate_table(rows, catalog)
    food = next(line for line in topics if "`food_restaurant`" in line).split("|")
    assert [c.strip() for c in food[3:6]] == ["1", "2", "3"]  # level 4, levels 4-5, any level
    housing = next(line for line in cands if "`housing_home`" in line).split("|")
    assert [c.strip() for c in housing[2:5]] == ["1", "2", "3"]

    out = tmp_path / "inv.csv"
    write_csv(rows, out)
    with out.open(encoding="utf-8") as fh:
        read = list(csv.DictReader(fh))
    usable_csv = [r for r in read if r["usable"] == "1"]
    assert len(usable_csv) == 3
    assert sum("food_restaurant" in r["topics"] for r in usable_csv) == 3
    assert sum("food_restaurant" in r["topics"] for r in read) == len(rows)  # tags are on every row

    md = render_md(rows, {"sitemap_urls": 7}, catalog, "phrase")
    assert "**Usable** (also licence_ok): **3**" in md
    section = md[md.index("## Level by topic") :].splitlines()
    level4 = next(line for line in section if line.startswith("| 4 |"))
    assert level4.split("|")[-2].strip() == "1"  # one usable level 4 row in the level matrix
