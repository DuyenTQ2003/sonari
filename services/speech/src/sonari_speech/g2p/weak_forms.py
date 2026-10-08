"""Other forms of a closed list of function words (`weak_forms.yaml`), as extra references.

The list is data, read once: a word that is not in the file has no other form. Each form is
one more way to say the word, scored beside the en-us and en-gb readings (scoring/accents.py).
"""

from collections.abc import Collection, Sequence
from pathlib import Path

import yaml

from sonari_speech.g2p.pronouncer import WordPron
from sonari_speech.g2p.text import normalize_word

WEAK_FORMS_PATH = Path(__file__).with_name("weak_forms.yaml")
Forms = dict[str, tuple[tuple[str, ...], ...]]
Reference = list[tuple[str, ...] | None]


def load_weak_forms(vocab: Collection[str], path: Path = WEAK_FORMS_PATH) -> Forms:
    """Word -> its other forms as token tuples. ValueError on a form the model cannot emit."""
    forms: Forms = {}
    for word, entries in yaml.safe_load(path.read_text("utf-8")).items():
        if word == "version":
            continue
        found = []
        for entry in entries:
            tokens = tuple(str(entry["tokens"]).split())
            if not tokens or not all(t in vocab for t in tokens):
                raise ValueError(f"{path.name}: {word!r} has a form outside the vocab: {tokens}")
            if len(entry) < 2:
                raise ValueError(f"{path.name}: {word!r} form {' '.join(tokens)} has no source")
            found.append(tokens)
        forms[normalize_word(word)] = tuple(found)
    return forms


def weak_references(words: Sequence[WordPron], forms: Forms) -> list[Reference]:
    """One reference per rank k: each word's k-th other form, None where it has fewer."""
    per_word = [forms.get(normalize_word(w.text), ()) for w in words]
    ranks = max(map(len, per_word), default=0)
    return [[f[k] if k < len(f) else None for f in per_word] for k in range(ranks)]
