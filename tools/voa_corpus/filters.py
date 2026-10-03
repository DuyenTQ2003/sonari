"""The level 4 filter and the buckets the report is drawn in. Thresholds are fixed here, before any
count was looked at, and each comes from a project document:

* length 250-1,200 words: `docs/level4-units-proposal.md` ("comfortable" for a unit's source);
* Flesch-Kincaid grade below 7.0: `voa_inventory/levels.py` (FK_BANDS: level 4 = B1);
* no editorial boilerplate: "as is" means nothing has to be cut out of the text;
* licence: ADR-0006 (VOA-staff byline, no wire text), via `voa_inventory/license.py`.
"""

from dataclasses import dataclass, field

MIN_WORDS, MAX_WORDS = 250, 1200
MAX_FK = 7.0
MIN_PASSAGE_WORDS = 100  # shorter pages are captions or stubs (rows.py: MIN_WORDS)
# Programmes about English itself, and fiction: not topical sources (docs/level4-units-proposal.md)
LESSONS_OR_FICTION = (
    "Words and Their Stories", "Everyday Grammar", "Ask a Teacher", "Let's Learn English",
    "American Stories",
)  # fmt: skip
FK_EDGES = (5, 7, 9, 11, 13)
LENGTH_EDGES = (1, 100, 250, 500, 750, 1200, 2000)
COVERAGE_EDGES = (0.85, 0.90, 0.95, 0.98)


@dataclass
class Passage:
    """One article page, measured. `vocab`: tokens per level A1..C2, unlisted, proper noun."""

    url: str
    program: str = ""
    words: int = 0
    sentences: int = 0
    fk: float | None = None  # Flesch-Kincaid without the boilerplate paragraphs
    fk_raw: float | None = None  # as extracted, boilerplate included
    cl: float | None = None  # Coleman-Liau, without the boilerplate paragraphs
    licence_ok: bool = False
    has_audio: bool = False
    html_ok: bool = True
    digest: str = ""
    duplicate: bool = False
    boiler: dict[str, int] = field(default_factory=dict)  # kind -> words
    kept: int = 0  # editorial words on lines that stay whole (ADR-0008): a label before speech
    vocab: tuple[int, ...] = (0,) * 8
    units: tuple[int, ...] = ()
    unlisted: dict[str, int] = field(default_factory=dict)
    loose: tuple[str, ...] = ()  # short paragraphs that no boilerplate rule caught

    @property
    def editorial_words(self) -> int:
        return sum(n for kind, n in self.boiler.items() if kind != "furniture")

    @property
    def removable(self) -> int:
        """Editorial words on lines a trim could remove whole."""
        return self.editorial_words - self.kept

    @property
    def coverage(self) -> float | None:
        """Share of the tokens that are not proper nouns that sit at A1-B2."""
        total = sum(self.vocab[:7])
        return sum(self.vocab[:4]) / total if total else None


def bucket(value: float, edges: tuple[float, ...]) -> str:
    """Label of the half-open bucket of `value`: '<5', '5-7', ..., '>=13'."""
    index = sum(value >= e for e in edges)
    if index == 0:
        return f"<{edges[0]:g}"
    return f">={edges[-1]:g}" if index == len(edges) else f"{edges[index - 1]:g}-{edges[index]:g}"


def blockers(
    p: Passage,
    words: tuple[int, int] = (MIN_WORDS, MAX_WORDS),
    max_fk: float = MAX_FK,
    cut_share: float = 0.0,
) -> list[str]:
    """Why a passage is not usable at level 4; empty when it is. Order = the funnel's.

    `cut_share` is the most that may be cut, as a share of the words, by removing whole lines
    (ADR-0008): frame words on a line that stays can never be cut, and the length window applies
    to the text that is left after the cut. At 0 nothing is cut: "as is".
    """
    left = p.words - (p.removable if cut_share > 0 else 0)
    checks = (
        ("not a passage", p.words < MIN_PASSAGE_WORDS or p.duplicate),
        ("length", not words[0] <= left <= words[1]),
        ("readability", p.fk is None or p.fk >= max_fk),
        ("boilerplate", p.kept > 0 or p.removable > cut_share * p.words),
        ("licence", not p.licence_ok),
    )
    return [name for name, failed in checks if failed]
