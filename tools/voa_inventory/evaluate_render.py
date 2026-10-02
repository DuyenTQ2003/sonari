"""Markdown for labels/evaluation.md: tagger quality and what the labels say about the corpus."""

from voa_inventory.evaluate import (
    MIN_SUPPORT,
    PREFIX,
    TIE,
    Cell,
    Corpus,
    f_beta,
    macro,
    measurable,
    pooled,
    wilson,
)
from voa_inventory.render import NEEDED, table
from voa_inventory.sample import SEED
from voa_inventory.topics import Catalog

LANGUAGE = "language_learning"


def _rate(value: float | None, num: int, den: int) -> str:
    return "n/a" if value is None else f"{value:.2f} ({num}/{den})"


def _cell(c: Cell, enough: bool) -> str:
    if enough:
        return (
            f"P {_rate(c.precision, c.tp, c.tp + c.fp)}<br>R {_rate(c.recall, c.tp, c.tp + c.fn)}"
        )
    return f"tp {c.tp} · fp {c.fp} · fn {c.fn}"


def per_topic(
    results: dict[str, dict[str, Cell]], ids: list[str], support: dict[str, int], ok: set[str]
) -> list[str]:
    body = [
        [f"`{t}`", str(support[t]), *(_cell(results[n][t], t in ok) for n in results)] for t in ids
    ]
    return table(["Topic", "Labelled", *results], body)


def _avg(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def summary(results: dict[str, dict[str, Cell]], plan: list[str], ok: list[str]) -> list[str]:
    rows = []
    for name, cells in results.items():
        mp, mr = macro(cells, ok)
        pool = pooled({t: cells[t] for t in plan})
        rows.append([
            name, _avg(mp), _avg(mr), _rate(pool.precision, pool.tp, pool.tp + pool.fp),
            _rate(pool.recall, pool.tp, pool.tp + pool.fn), f"{f_beta(pool):.2f}",
        ])  # fmt: skip
    header = ["Tagger", "Macro P", "Macro R", "Pooled P (8 plan)", "Pooled R (8 plan)", "F0.5"]
    return table(header, rows)


def _share(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.0%} (95% interval {lo:.0%}-{hi:.0%})"


def corpus_finding(labels: dict[str, str], catalog: Catalog, corpus: Corpus) -> str:
    n = len(labels)
    plan = [t.id for t in catalog.topics]
    lang = sum(v == LANGUAGE for v in labels.values())
    none_n = sum(v == "none" for v in labels.values())
    on_plan = sum(v in plan for v in labels.values())
    scale = corpus.usable_level4 / corpus.coverage if corpus.coverage else 0.0
    body, unconfirmed = [], []
    for t in catalog.topics:
        k = sum(v == t.id for v in labels.values())
        lo, hi = wilson(k, n)
        if lo * scale < NEEDED:
            unconfirmed.append(f"`{t.id}` ({k} labelled, at most {hi * scale:.0f} whole site)")
        body.append([
            str(t.unit), f"`{t.id}`", str(k), f"{lo * corpus.usable_level4:.0f}-"
            f"{hi * corpus.usable_level4:.0f}", f"{lo * scale:.0f}-{hi * scale:.0f}",
        ])  # fmt: skip
    rows = "\n".join(
        table(["Unit", "Topic", "Labelled", "Crawl, usable lv 4", "Whole site, usable lv 4"], body)
    )
    supported = len(plan) - len(unconfirmed)
    sizes = {t: sum(v == t for v in labels.values()) for t in plan}
    top = max(plan, key=lambda t: sizes[t])
    second = max(v for t, v in sizes.items() if t != top)
    return f"""### Finding: {lang} of {n} usable level 4 pages teach English, not a life topic

Of the {n} labelled usable level 4 pages, `{LANGUAGE}` (pages about English itself: grammar,
idioms, *Let's Learn English* lessons) is {_share(lang, n)}. Those pages cannot be a unit's
life-topic passage. One of the eight plan topics is {_share(on_plan, n)}; a replacement
candidate other than `{LANGUAGE}` is {_share(n - lang - none_n - on_plan, n)}; `none` is
{none_n}.

The crawl holds {corpus.usable_level4} usable level 4 pages at {corpus.coverage:.1%} coverage,
roughly {scale:.0f} on the whole site. Each plan topic's labelled share, as a 95% interval,
scaled to those pools (owner labels, not tagger output):

{rows}

A unit needs one source passage and the report asks for {NEEDED} per topic. The lower end of
the whole-site interval reaches {NEEDED} for **{supported} of {len(plan)}** plan topics. Not
confirmed: {", ".join(unconfirmed) or "none"}. Outside `{top}`, no plan topic has more
than {second} of {n} labelled pages, so finding a unit's passage means reading pages: the
taggers above miss most of them.
"""


def _precision(c: Cell) -> str:
    lo, hi = wilson(c.tp, c.tp + c.fp)
    return f"{c.tp} of {c.tp + c.fp} tags correct (95% interval {lo:.2f}-{hi:.2f})"


def bug_cost(
    results: dict[str, dict[str, Cell]],
    labels: dict[str, str],
    plan: list[str],
    chosen: str,
    placeholder: int,
) -> str:
    """What the placeholder bug and the old tagger did to the published counts."""
    cells = results[PREFIX]
    over = [t for t in plan if cells[t].tp + cells[t].fp > cells[t].tp + cells[t].fn]
    under = [t for t in plan if cells[t].tp + cells[t].fp < cells[t].tp + cells[t].fn]

    def side(ids: list[str]) -> str:
        return ", ".join(
            f"`{t}` {cells[t].tp + cells[t].fp} tagged vs {cells[t].tp + cells[t].fn} labelled"
            for t in ids
        )

    if over and under:
        bound = f"they were not upper bounds. Too high: {side(over)}. Too low: {side(under)}."
    elif over:
        bound = f"they were upper bounds: {side(over)}."
    else:
        bound = f"they were not upper bounds; they were too low: {side(under) or 'no topic'}."
    before, after, now = (
        pooled({t: results[n][t] for t in plan}) for n in (PREFIX, "keyword-v1", chosen)
    )
    return f"""**Every count published before the fix was measured on placeholder text and is
void.** For {placeholder} of the {len(labels)} labelled pages the pre-fix first paragraph was player
or download boilerplate, so the old tagger in effect read the title only. On these pages,
over the eight plan topics: {bound}

What the bug cost, pooled over the plan topics: `{PREFIX}` {_precision(before)}, recall
{_avg(before.recall)}; the same tagger on corrected text {_precision(after)}, recall
{_avg(after.recall)}; `{chosen}` {_precision(now)}, recall {_avg(now.recall)}. The bug cost
recall, not precision; the wrong tags come from the taggers themselves. With
{_avg(now.precision)} of `{chosen}` tags correct and {_avg(now.recall)} of labelled pages found,
a per-topic tagger count below is a list of pages to read, not a supply figure."""


def render(
    results: dict[str, dict[str, Cell]],
    labels: dict[str, str],
    catalog: Catalog,
    chosen: str,
    corpus: Corpus,
    placeholder: int,
) -> str:
    plan = [t.id for t in catalog.topics]
    cands = [c.id for c in catalog.candidates]
    support = {t: sum(v == t for v in labels.values()) for t in plan + cands}
    ok = measurable(labels, plan + cands)
    plan_support = sum(support[t] for t in plan)
    top = max(plan, key=lambda t: support[t])
    small = ", ".join(f"`{t}` {support[t]}" for t in plan if t not in ok)
    return f"""### How the tagger was chosen

Four taggers are scored on the same labelled pages. `{PREFIX}` is the first tagger (bare
keywords, `topics_v1.yaml`) fed the first paragraph as extracted before the audio-player fix,
which for most pages was the placeholder "No media source currently available"; it is how
every count before the fix was made. `keyword-v1` is the same tagger on the corrected text.
`phrase` (phrases plus stop patterns) and `embedding` (bge-m3 similarity to a description per
topic) were built and fixed in `topics.yaml` before any label existed.

**Labelled set: {len(labels)} usable level 4 pages, drawn at random (seed {SEED}), each given
one label by one person (the owner).** There is no second labeller, so label noise is
unmeasured. Units 1 and 5 follow the PLAN-v7 4.1 swap (`technology_devices`,
`nature_environment`); the phrase lists and the similarity floor were not changed.

A rate is shown only for a label with at least {MIN_SUPPORT} labelled pages
(**{", ".join(f"`{t}` {support[t]}" for t in ok) or "none"}**). Every other row shows raw
counts (tp correct tags, fp wrong tags, fn missed pages): the sample is too small to measure
it. Among the plan topics that is {small}.

Plan topics (unit order):

{chr(10).join(per_topic(results, plan, support, set(ok)))}

Replacement candidates:

{chr(10).join(per_topic(results, cands, support, set(ok)))}

Macro P and R average only the {len(ok)} measurable labels above, unweighted. Pooled P and R
add up the counts over the eight plan topics ({plan_support} labelled pages, {support[top]} of
them `{top}`, so the pool mostly measures that one topic):

{chr(10).join(summary(results, plan, ok))}

Rule (fixed before labelling): the higher pooled F0.5 of `phrase` and `embedding` on the
eight plan topics, `phrase` if within {TIE}. **Chosen: `{chosen}`.**

{bug_cost(results, labels, plan, chosen, placeholder)}

{corpus_finding(labels, catalog, corpus)}"""
