"""Score the classifier against the hand labels of the seeded sample (`make voa-classify-validate`).

The sample is stratified by the type the classifier gave, so a plain error rate over it would count
the small types too much. The corpus-weighted rate weighs each stratum by its share of the 724
passages and draws each stratum's error rate from a Jeffreys posterior, so a stratum with no error
still contributes doubt. The labels are in docs/reports/voa-classify-labels.tsv.
"""

import argparse
import random
from collections import Counter
from pathlib import Path

from voa_corpus.classify import USABLE_TYPES
from voa_corpus.classify_report import ALLOC, DEFAULT, SEED, flags, load, table

LABELS = Path(__file__).parents[2] / "docs/reports/voa-classify-labels.tsv"


def in_path(kind: str) -> bool:
    """Only these types can reach the reading path."""
    return kind in USABLE_TYPES


# key: (name, which predicted types are in scope, is this passage an error)
MEASURES = {
    "type": ("type (8-way)", lambda k: True, lambda r, h: r["type"] != h[0]),
    "usable": (
        "usable type (explainer/news vs the rest)",
        lambda k: True,
        lambda r, h: in_path(r["type"]) != in_path(h[0]),
    ),
    "flags": (
        "any safety flag, all types",
        lambda k: True,
        lambda r, h: bool(flags(r)) != bool(h[1]),
    ),
    "path flags": (
        "any safety flag, explainer/news only",
        in_path,
        lambda r, h: bool(flags(r)) != bool(h[1]),
    ),
}


def read_labels(path: Path) -> dict[str, tuple[str, frozenset[str], str]]:
    hand = {}
    for line in path.read_text("utf-8").splitlines():
        if line and not line.startswith(("#", "id\t")):
            i, kind, marked, note = [*line.split("\t"), ""][:4]
            hand[i] = (kind, frozenset(marked.split(",")) - {"-"}, note)
    return hand


def weighted(per: dict[str, list[int]], size: Counter, draws: int = 20000) -> tuple:
    """Median and 2.5-97.5% range of the corpus-weighted error rate.

    `per` maps a stratum to [errors, read]."""
    strata = {k: v for k, v in per.items() if v[1]}
    total, rng = sum(size[k] for k in strata), random.Random(SEED)
    sims = sorted(
        sum(size[k] * rng.betavariate(e + 0.5, n - e + 0.5) for k, (e, n) in strata.items()) / total
        for _ in range(draws)
    )
    return sims[draws // 2], sims[int(0.025 * draws)], sims[int(0.975 * draws)]


def validate(rows: list[dict], labels: Path) -> str:
    by_id, hand = {r["id"]: r for r in rows}, read_labels(labels)
    size = Counter(r["type"] for r in rows)
    per = {key: {t: [0, 0] for t in ALLOC if m[1](t)} for key, m in MEASURES.items()}
    misses: dict[str, list[str]] = {}
    for i, h in hand.items():
        r = by_id[i]
        for key, (_, scope, bad) in MEASURES.items():
            if scope(r["type"]):
                per[key][r["type"]][0] += bad(r, h)
                per[key][r["type"]][1] += 1
                if bad(r, h) and key != "path flags":
                    misses.setdefault(i, []).append(key)
    summary = []
    for key, (name, _, _) in MEASURES.items():
        errors, read = (sum(v[j] for v in per[key].values()) for j in (0, 1))
        med, lo, hi = weighted(per[key], size)
        summary.append([name, f"{errors}/{read}", f"{med:.1%} ({lo:.1%}-{hi:.1%})"])
    path = [(by_id[i], h) for i, h in hand.items() if in_path(by_id[i]["type"])]
    marked = sum(bool(h[1]) for _, h in path)
    alarms = sum(bool(flags(r)) and not h[1] for r, h in path)
    missed = sum(not flags(r) and bool(h[1]) for r, h in path)
    swaps = sum(
        in_path(by_id[i]["type"]) and in_path(hand[i][0])
        for i, ms in misses.items()
        if "type" in ms
    )
    lines = [
        f"{len(hand)} passages read by hand, seed {SEED}",
        "",
        table(["measure", "errors", "corpus-weighted median (95% interval)"], summary),
        "",
        f"Type misses that only swap explainer and news item: {swaps} of "
        f"{sum('type' in ms for ms in misses.values())}.",
        f"Flags on {len(path)} explainer/news passages: by hand {marked}, by classifier "
        f"{marked + alarms - missed}, false alarms {alarms}, misses {missed}.",
        "",
        "Misses (type / usable type / flags):",
    ]
    for i, ms in misses.items():
        r, h = by_id[i], hand[i]
        lines.append(
            f"- {i} {r['title'][:50]!r} [{', '.join(ms)}]: tagged {r['type']} ({r['rule']}) "
            f"flags {sorted(flags(r)) or '-'}; by hand {h[0]} {sorted(h[1]) or '-'}. {h[2]}"
        )
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", type=Path, default=DEFAULT)
    ap.add_argument("--labels", type=Path, default=LABELS)
    a = ap.parse_args()
    print(validate(load(a.file), a.labels))


if __name__ == "__main__":
    main()
