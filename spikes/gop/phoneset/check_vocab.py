"""Assert that every token the ARPAbet -> espeak table can emit is in the model vocab.

Usage (from the repo root):
    uv run --directory spikes/gop python -m phoneset.check_vocab [--vocab PATH]

The vocab is downloaded from the Hugging Face hub unless --vocab points at a local
vocab.json. Exit code 1 lists every missing token.
"""

import argparse
import json
import sys
from pathlib import Path

from phoneset.mapping import load_table, mapped_tokens

MODEL = "facebook/wav2vec2-lv-60-espeak-cv-ft"


def load_vocab(path: Path | None = None) -> dict[str, int]:
    if path is None:
        from huggingface_hub import hf_hub_download

        path = Path(hf_hub_download(MODEL, "vocab.json"))
    return json.loads(path.read_text("utf-8"))


def missing_tokens(vocab: dict[str, int]) -> list[str]:
    return sorted(tok for tok in mapped_tokens(load_table()) if tok not in vocab)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vocab", type=Path, help="local vocab.json (default: download)")
    args = parser.parse_args()
    vocab = load_vocab(args.vocab)
    tokens = mapped_tokens(load_table())
    missing = missing_tokens(vocab)
    print(f"{len(tokens) - len(missing)}/{len(tokens)} mapped tokens are in the vocab")
    if missing:
        print("MISSING:", " ".join(f"{tok!r} (U+{ord(tok[0]):04X}...)" for tok in missing))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
