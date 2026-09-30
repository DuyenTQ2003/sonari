"""Round trip: g2p_en + ARPAbet->espeak table vs espeak-ng, word by word.

Usage (from the repo root):
    uv run --directory spikes/gop python -m phoneset.roundtrip_test
    uv run --directory spikes/gop python -m phoneset.roundtrip_test --words FILE --no-report

Writes phoneset/REPORT.md. Exits 1 when a mismatch that survives the fold rules has no
label in mismatch_labels.yaml, or is labelled "mapping bug": mapping bugs must be fixed
in the table, not documented.
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from phoneset.compare import diff_ops, explaining_folds, fold, strip_stress
from phoneset.mapping import to_espeak

HERE = Path(__file__).parent
WORDS = HERE / "ngsl_head200.txt"
LABELS = HERE / "mismatch_labels.yaml"
REPORT = HERE / "REPORT.md"
CLASSES = ("accent variant", "g2p error", "mapping bug")
NLTK_RESOURCES = ("averaged_perceptron_tagger_eng", "cmudict")


@dataclass
class Row:
    word: str
    arpabet: list[str]
    mapped: list[str]
    espeak: list[str]
    tags: list[str] = field(default_factory=list)
    in_cmudict: bool = True

    @property
    def strict(self) -> bool:
        return self.mapped == self.espeak

    @property
    def folded(self) -> bool:
        return fold(self.mapped) == fold(self.espeak)


def read_words(path: Path) -> list[str]:
    lines = (line.strip() for line in path.read_text("utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def load_g2p():
    import nltk

    data = Path(os.environ.get("DATA_DIR", "~/sonari-data")).expanduser() / "nltk_data"
    data.mkdir(parents=True, exist_ok=True)
    nltk.data.path.insert(0, str(data))
    for resource in NLTK_RESOURCES:
        nltk.download(resource, download_dir=str(data), quiet=True)
    from g2p_en import G2p

    return G2p()


def run(words: list[str]) -> list[Row]:
    from phonemizer.backend import EspeakBackend
    from phonemizer.separator import Separator

    g2p = load_g2p()
    backend = EspeakBackend("en-us", with_stress=True)
    ipa = backend.phonemize(words, separator=Separator(phone=" ", word=""), strip=True)
    rows = []
    for word, espeak in zip(words, ipa, strict=True):
        arpabet = [p for p in g2p(word) if re.fullmatch(r"[A-Z]{1,2}[012]?", p)]
        mapped, spoken = to_espeak(arpabet), strip_stress(espeak.split())
        tags = explaining_folds(mapped, spoken)
        rows.append(Row(word, arpabet, mapped, spoken, tags, word.lower() in g2p.cmu))
    return rows


def pct(n: int, total: int) -> str:
    return f"{n}/{total} ({100 * n / total:.1f}%)"


def versions() -> str:
    import subprocess
    from importlib.metadata import version

    out = subprocess.run(["espeak-ng", "--version"], capture_output=True, text=True, check=True)
    espeak = re.search(r"\d+\.\d+(\.\d+)?", out.stdout)
    return (
        f"g2p_en {version('g2p_en')}, phonemizer {version('phonemizer')}, "
        f"espeak-ng {espeak.group(0) if espeak else '?'}"
    )


def spike_table() -> tuple[list[str], int]:
    """Compare the espeak tokens the P02 spike wrote by hand with this table."""
    from run_gop import LEXICON  # importing runs no model code

    lines = ["| Word | Spike (by hand) | Table | espeak-ng | Agreement |", "|---|---|---|---|---|"]
    disagree = 0
    for row in run(list(LEXICON)):
        hand = LEXICON[row.word]
        ok = hand == row.mapped == row.espeak
        disagree += not ok
        lines.append(
            f"| {row.word} | {' '.join(hand)} | {' '.join(row.mapped)} "
            f"| {' '.join(row.espeak)} | {'all equal' if ok else 'DISAGREE'} |"
        )
    return lines, disagree


def residual_table(rows: list[Row], labels: dict) -> list[str]:
    lines = [
        "| Word | ARPAbet | Table | espeak-ng | Differences | Class | Why |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r.folded:
            continue
        label = labels[r.word]
        diffs = "; ".join(f"{a or '∅'} → {b or '∅'}" for a, b in diff_ops(r.mapped, r.espeak))
        lines.append(
            f"| {r.word} | {' '.join(r.arpabet)} | {' '.join(r.mapped)} | {' '.join(r.espeak)} "
            f"| {diffs} | {label['class']} | {label['note']} |"
        )
    return lines


def variant_table(rows: list[Row]) -> list[str]:
    lines = ["| Word | Table | espeak-ng | Folds that explain it |", "|---|---|---|---|"]
    for r in rows:
        if not r.strict and r.folded:
            lines.append(
                f"| {r.word} | {' '.join(r.mapped)} | {' '.join(r.espeak)} | {', '.join(r.tags)} |"
            )
    return lines


def check_labels(rows: list[Row], labels: dict) -> list[str]:
    problems = []
    for r in rows:
        if r.folded:
            continue
        label = labels.get(r.word)
        if label is None:
            problems.append(f"unlabelled mismatch: {r.word}: {r.mapped} vs {r.espeak}")
        elif label["class"] not in CLASSES:
            problems.append(f"bad class for {r.word}: {label['class']}")
        elif label["class"] == "mapping bug":
            problems.append(f"mapping bug left in the table: {r.word}")
    return problems


def build_report(rows: list[Row], labels: dict) -> str:
    n = len(rows)
    strict = sum(r.strict for r in rows)
    folded = sum(r.folded for r in rows)
    template = (HERE / "REPORT.template.md").read_text("utf-8")
    spike_lines, spike_disagree = spike_table()
    fields = {
        "versions": versions(),
        "n": str(n),
        "strict": pct(strict, n),
        "folded": pct(folded, n),
        "residual": str(n - folded),
        "oov": str(sum(not r.in_cmudict for r in rows)),
        "spike_disagree": str(spike_disagree),
        "spike_table": "\n".join(spike_lines),
        "variant_table": "\n".join(variant_table(rows)),
        "residual_table": "\n".join(residual_table(rows, labels)),
    }
    return template.format(**fields)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--words", type=Path, default=WORDS)
    parser.add_argument("--no-report", action="store_true", help="print numbers only")
    args = parser.parse_args()
    rows = run(read_words(args.words))
    labels = yaml.safe_load(LABELS.read_text("utf-8")) if LABELS.exists() else {}
    n = len(rows)
    strict, folded = sum(r.strict for r in rows), sum(r.folded for r in rows)
    print(f"strict {pct(strict, n)}, folded {pct(folded, n)}")
    problems = check_labels(rows, labels)
    for problem in problems:
        print(problem)
    if not args.no_report and not problems:
        REPORT.write_text(build_report(rows, labels), "utf-8")
        print(f"wrote {REPORT}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
