"""Markdown for docs/reports/score-native-calibration.md from the scored native JSONL.

make score-native-report   (python -m score_eval.report <native-....jsonl>)
"""

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from score_eval import analyse as a

# CMUdict's first variant of these is the strong form; read speech uses the weak (tə, wəz, ən).
WEAK_FORMS = frozenset({"to", "was", "and"})
_FUNCTION = "the a an to of and in on at for is was are were be been that this it he she his her"
_MORE = "you i we they them him with as by from or but not so have has had do did"
FUNCTION_WORDS = frozenset(f"{_FUNCTION} {_MORE}".split())
QS = (0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.25, 0.5)
Clips = list[dict[str, Any]]


def row(*cells: object) -> str:
    return "| " + " | ".join(map(str, cells)) + " |"


def rates(clips: Clips, t: float) -> str:
    counts = a.per_clip(clips, t)
    n, hit = len(counts), sum(c > 0 for c in counts.values())
    lo, hi = a.bootstrap(clips, t)
    share = f"{a.wrong_share(clips, t):.2%} ({lo:.2%}-{hi:.2%})"
    return row(t, share, f"{sum(counts.values()) / n:.2f}", f"{hit} of {n} ({hit / n:.0%})")


def split_half(clips: Clips) -> list[str]:
    speakers = sorted({c["speaker"] for c in clips})
    halves = [set(speakers[0::2]), set(speakers[1::2])]
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
    weak = sum(p.word.lower() in WEAK_FORMS for p in wrong)
    top = Counter(p.expected for p in wrong).most_common(8)
    return [
        f"{len(wrong)} wrong; {func} ({func / len(wrong):.0%}) in function words, which hold "
        f"{func_all / len(ps):.0%} of the phonemes; {weak} ({weak / len(wrong):.0%}) in "
        f"{'/'.join(sorted(WEAK_FORMS))} alone.",
        "",
        "- phonemes (wrong / seen): " + ", ".join(f"{e} {n}/{seen[e]}" for e, n in top),
        "- words: "
        + ", ".join(f"{w} {n}" for w, n in Counter(p.word.lower() for p in wrong).most_common(12)),
        "- expected→heard: "
        + ", ".join(
            f"{k} {n}" for k, n in Counter(f"{p.expected}→{p.heard}" for p in wrong).most_common(8)
        ),
    ]


def native(raw: Clips) -> str:
    clips = [c for c in raw if "words" in c]
    gops = [p.gop for p in a.phonemes(clips, a.V1_WRONG_BELOW)]
    point, v2 = a.propose(clips), a.propose_upper(clips)
    rest = a.without_words(clips, WEAK_FORMS)
    t_rest = a.propose(rest)
    out = [
        f"{len(clips)} utterances ({len(raw) - len(clips)} refused), "
        f"{len({c['speaker'] for c in clips})} speakers, {len(gops)} phonemes.",
        "",
        "### GOP distribution (each word on its v1-chosen accent)",
        "",
        row("quantile", *(f"{q:.1%}" for q in QS)),
        row(*["---"] * (len(QS) + 1)),
        row("GOP", *(f"{v:+.2f}" for v in a.quantiles(gops, QS).values())),
        "",
        f"At or below 0 (not correct): {sum(g <= 0 for g in gops) / len(gops):.1%}.",
        "",
        "### Native phonemes marked wrong (95% bootstrap interval over utterances)",
        "",
        row("wrong below", "phonemes wrong", "wrong per utterance", "utterances with any"),
        row(*["---"] * 4),
        *(rates(clips, t) for t in (a.V1_WRONG_BELOW, point, v2)),
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
        f"What-if, not a scoring change: without {'/'.join(sorted(WEAK_FORMS))}, "
        f"{a.wrong_share(rest, a.V1_WRONG_BELOW):.2%} are wrong at {a.V1_WRONG_BELOW}, and under "
        f"1% needs only {t_rest} ({a.wrong_share(rest, t_rest):.2%}).",
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


if __name__ == "__main__":
    lines = Path(sys.argv[1]).read_text("utf-8").splitlines()
    print(native([json.loads(line) for line in lines if line]), end="")
