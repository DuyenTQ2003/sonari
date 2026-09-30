"""ARPAbet (with stress digits) -> espeak IPA tokens of the wav2vec2 phoneme vocab.

Pure python plus PyYAML, so the unit tests need neither torch nor g2p_en. The table is
`arpabet_to_espeak.yaml`; every choice that depends on the accent is commented there.
"""

import re
from collections.abc import Sequence
from functools import cache
from pathlib import Path

import yaml

TABLE_PATH = Path(__file__).with_name("arpabet_to_espeak.yaml")
_PHONE = re.compile(r"^([A-Z]{1,2})([012])?$")
VOWELS = frozenset(
    {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW"}
)


@cache
def load_table(path: Path = TABLE_PATH) -> dict:
    return yaml.safe_load(path.read_text("utf-8"))


def split_stress(phone: str) -> tuple[str, int | None]:
    """'IH1' -> ('IH', 1); 'TH' -> ('TH', None). Raises ValueError on anything else."""
    m = _PHONE.match(phone)
    if m is None:
        raise ValueError(f"not an ARPAbet phone: {phone!r}")
    return m.group(1), None if m.group(2) is None else int(m.group(2))


def to_espeak(phones: Sequence[str], table: dict | None = None) -> list[str]:
    """Map the ARPAbet phones of ONE word to espeak IPA tokens."""
    table = table or load_table()
    parsed = [split_stress(p) for p in phones]
    for base, _ in parsed:
        if base not in table["phones"]:
            raise ValueError(f"unknown ARPAbet phone: {base!r}")
    out: list[str] = []
    i = 0
    while i < len(parsed):
        merged = _merge(parsed, i, table)
        if merged is not None:
            out.extend(merged)
            i += 2
            continue
        base, stress = parsed[i]
        nxt = parsed[i + 1][0] if i + 1 < len(parsed) else None
        out.extend(_single(base, stress, nxt, table))
        i += 1
    return out


def _merge(parsed: list[tuple[str, int | None]], i: int, table: dict) -> list[str] | None:
    """Tokens for the phone pair starting at i when espeak fuses it, else None."""
    if i + 1 >= len(parsed):
        return None
    (base, _), (nxt, nxt_stress) = parsed[i], parsed[i + 1]
    if nxt_stress == 0 and (tokens := table["vowel_merges"].get(f"{base}+{nxt}")):
        return tokens
    rule = table["r_coloured"].get(base)
    if nxt != "R" or rule is None:
        return None
    after = parsed[i + 2][0] if i + 2 < len(parsed) else None
    return rule.get("before_vowel") if after in VOWELS else rule["token"]


def _single(base: str, stress: int | None, nxt: str | None, table: dict) -> list[str]:
    if stress == 0 and base == "IY":
        rule = table["unstressed_iy"]
        if nxt is None:
            return rule["word_final"]
        return rule["before_vowel" if nxt in VOWELS else "elsewhere"]
    source = table["unstressed"] if stress == 0 and base in table["unstressed"] else table["phones"]
    if base == "ER" and nxt in VOWELS:
        return [*source[base], *table["er_before_vowel"]]
    return source[base]


def mapped_tokens(table: dict | None = None) -> set[str]:
    """Every espeak token the table can emit."""
    table = table or load_table()
    tokens: set[str] = set()
    for key in ("phones", "unstressed", "vowel_merges"):
        tokens.update(t for toks in table[key].values() for t in toks)
    for rule in table["unstressed_iy"].values():
        tokens.update(rule)
    for rule in table["r_coloured"].values():
        tokens.update(rule["token"], rule.get("before_vowel", []))
    tokens.update(table["er_before_vowel"])
    return tokens
