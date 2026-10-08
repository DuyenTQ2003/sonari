"""Markdown for the native-speech reports from the scored native JSONL.

make score-native   (python -m score_eval.report <native-....jsonl>)

Without `--wrong-below` the v2 threshold is proposed from the file by the stated rule; with
it, that threshold is only measured (a held-out file; `--without` drops the utterances that
are also in the file the threshold was chosen on). The "before" rows score the same audio
against en-us and en-gb only, which is what PR #51 measured.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from score_eval import analyse as a

# The words of g2p/weak_forms.yaml (this module runs without the service's packages).
LISTED = frozenset(["to", "was", "and", "the", "a", "of", "for", "at", "can", "them"])
_FUNCTION = "the a an to of and in on at for is was are were be been that this it he she his her"
_MORE = "you i we they them him with as by from or but not so have has had do did"
FUNCTION_WORDS = frozenset(f"{_FUNCTION} {_MORE}".split())
QS = (0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.25, 0.5)
Clips = list[dict[str, Any]]


def row(*cells: object) -> str:
    return "| " + " | ".join(map(str, cells)) + " |"


def rates(label: str, clips: Clips, t: float) -> str:
    counts = a.per_clip(clips, t)
    n, hit = len(counts), sum(c > 0 for c in counts.values())
    lo, hi = a.bootstrap(clips, t)
    share = f"{a.wrong_share(clips, t):.2%} ({lo:.2%}-{hi:.2%})"
    return row(label, t, share, f"{sum(counts.values()) / n:.2f}", f"{hit} of {n} ({hit / n:.0%})")


def speakers(clips: Clips) -> list[str]:
    return sorted({c["speaker"] for c in clips})


def split_half(clips: Clips) -> list[str]:
    names = speakers(clips)
    halves = [set(names[0::2]), set(names[1::2])]
    out = []
    for i, fit_on in enumerate(halves):
        t = a.propose([c for c in clips if c["speaker"] in fit_on])
        held = [c for c in clips if c["speaker"] in halves[1 - i]]
        out.append(row(f"half {'AB'[i]}", t, f"{a.wrong_share(held, t):.2%}"))
    return out


def who(clips: Clips, t: float) -> list[str]:
    ps = list(a.phonemes(clips, t))
    wrong = [p for p in ps if p.verdict == "wrong"]
    seen = Counter(p.expected for p in ps)
    func = sum(p.word.lower() in FUNCTION_WORDS for p in wrong)
    func_all = sum(p.word.lower() in FUNCTION_WORDS for p in ps)
    listed = sum(p.word.lower() in LISTED for p in wrong)
    top = Counter(p.expected for p in wrong).most_common(8)
    words = Counter(p.word.lower() for p in wrong)
    top10 = sum(n for _, n in words.most_common(10))
    shares = {s: a.wrong_share([c for c in clips if c["speaker"] == s], t) for s in speakers(clips)}
    worst = max(shares, key=lambda s: shares[s])
    return [
        f"{len(wrong)} wrong; {func} ({func / len(wrong):.0%}) in function words, which hold "
        f"{func_all / len(ps):.0%} of the phonemes; {listed} ({listed / len(wrong):.0%}) in the "
        f"ten listed words; the top 10 words hold {top10}.",
        "",
        "- phonemes (wrong / seen): " + ", ".join(f"{e} {n}/{seen[e]}" for e, n in top),
        "- words: " + ", ".join(f"{w} {n}" for w, n in words.most_common(12)),
        "- expected→heard: "
        + ", ".join(
            f"{k} {n}" for k, n in Counter(f"{p.expected}→{p.heard}" for p in wrong).most_common(8)
        ),
        f"- speakers: wrong share from {min(shares.values()):.2%} to {shares[worst]:.2%} "
        f"({worst}); median {sorted(shares.values())[len(shares) // 2]:.2%}",
    ]


def forms(clips: Clips, t: float) -> list[str]:
    """For each listed word, the forms the service would have kept and how often."""
    seen: dict[str, Counter[str]] = {}
    for c in clips:
        for w in c["words"]:
            if (key := w["text"].lower()) in LISTED:
                _, rows = a.choose(w, t)
                seen.setdefault(key, Counter())[" ".join(p["expected"] for p in rows)] += 1
    return [
        row(
            k,
            sum(n.values()),
            ", ".join(f"{f} {c / sum(n.values()):.0%}" for f, c in n.most_common()),
        )
        for k, n in sorted(seen.items(), key=lambda kv: -sum(kv[1].values()))
    ]


def sentences(clips: Clips, t: float, lo: int = 6, hi: int = 14) -> list[str]:
    counts = a.per_clip(clips, t)
    sized = [(len(c["words"]), counts[c["id"]]) for c in clips if "words" in c]
    rate = sum(counts.values()) / sum(n for n, _ in sized)
    inside = [k for n, k in sized if lo <= n <= hi]
    hit = sum(k > 0 for k in inside)
    return [
        f"- wrong per word: {rate:.3f}, so {rate * lo:.2f} in a {lo}-word and {rate * hi:.2f} in a "
        f"{hi}-word sentence, if wrongs fell evenly over words",
        f"- measured on the {len(inside)} native utterances of {lo}-{hi} words: "
        f"{sum(inside) / len(inside):.2f} wrong per utterance, "
        f"{hit} of {len(inside)} ({hit / len(inside):.0%}) with at least one",
    ]


def native(raw: Clips, fixed: float | None = None) -> str:
    clips = [c for c in raw if "words" in c]
    before = a.without_weak(clips)
    gops = [p.gop for p in a.phonemes(clips, a.V1_WRONG_BELOW)]
    old = a.propose_upper(before)
    point, v2 = a.propose(clips), fixed if fixed is not None else a.propose_upper(clips)
    out = [
        f"{len(clips)} utterances ({len(raw) - len(clips)} refused), "
        f"{len(speakers(clips))} speakers, {len(gops)} phonemes.",
        "",
        "### GOP distribution (each word on the reference chosen at -3.4)",
        "",
        row("quantile", *(f"{q:.1%}" for q in QS)),
        row(*["---"] * (len(QS) + 1)),
        row("GOP", *(f"{v:+.2f}" for v in a.quantiles(gops, QS).values())),
        "",
        f"At or below 0 (not correct): {sum(g <= 0 for g in gops) / len(gops):.1%}.",
        "",
        "### Native phonemes marked wrong (95% bootstrap interval over utterances)",
        "",
        row(
            "references",
            "wrong below",
            "phonemes wrong",
            "wrong per utterance",
            "utterances with any",
        ),
        row(*["---"] * 5),
        *(rates("en-us + en-gb", before, t) for t in sorted({a.V1_WRONG_BELOW, old}, reverse=True)),
        *(
            rates("+ weak forms", clips, t)
            for t in sorted({a.V1_WRONG_BELOW, point, v2}, reverse=True)
        ),
        "",
        f"The rule picks {v2}"
        + (" (fixed, not proposed)" if fixed is not None else "")
        + f"; without weak forms it picked {old}.",
        "",
        "Split half by speaker (fit on one half, rate on the other):",
        "",
        row("fitted on", "threshold", "wrong on the other half"),
        row(*["---"] * 3),
        *split_half(clips),
    ]
    for t in (a.V1_WRONG_BELOW, v2):
        out += ["", f"### Who is marked wrong at {t}", "", *who(clips, t)]
    out += [
        "",
        f"### Forms kept for the listed words at {v2}",
        "",
        row("word", "seen", "form (share)"),
        row(*["---"] * 3),
        *forms(clips, v2),
        "",
        f"### Expected native wrongs per practice sentence at {v2}",
        "",
        *sentences(clips, v2),
        "",
        "### Do native wrongs fail together as whole words?",
        "",
        row("wrong below", "words with most wrong", "expected if independent", "wrongs in them"),
        row(*["---"] * 4),
    ]
    for t in (a.V1_WRONG_BELOW, v2):
        c = a.collapse(clips, t)
        out.append(row(t, c.observed, f"{c.expected:.2f}", f"{c.wrong_in_collapsed} of {c.wrong}"))
    return "\n".join(out) + "\n"


def read(path: Path) -> Clips:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--wrong-below", type=float)
    parser.add_argument("--without", type=Path)
    args = parser.parse_args()
    seen = {c["id"] for c in read(args.without)} if args.without else set()
    print(native([c for c in read(args.jsonl) if c["id"] not in seen], args.wrong_below), end="")
