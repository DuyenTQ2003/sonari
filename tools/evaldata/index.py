"""Index LibriSpeech dev-clean transcripts into a dataframe cached as parquet.

Columns: utterance_id, speaker_id, chapter_id, flac_path (relative to DATA_DIR), text,
duration (seconds).
"""

import argparse
from pathlib import Path

import pandas as pd
import soundfile as sf
from common import data_dir, librispeech_dir

SUBSET = "dev-clean"


def index_path() -> Path:
    return librispeech_dir() / f"{SUBSET}.index.parquet"


def build_index() -> pd.DataFrame:
    root = librispeech_dir() / SUBSET
    if not root.is_dir():
        raise SystemExit(f"{root} not found; run tools/evaldata/fetch_librispeech.py first")
    rows = []
    for trans in sorted(root.glob("*/*/*.trans.txt")):
        for line in trans.read_text(encoding="utf-8").splitlines():
            utterance_id, text = line.split(" ", 1)
            speaker_id, chapter_id, _ = utterance_id.split("-")
            flac = trans.parent / f"{utterance_id}.flac"
            rows.append(
                {
                    "utterance_id": utterance_id,
                    "speaker_id": speaker_id,
                    "chapter_id": chapter_id,
                    "flac_path": str(flac.relative_to(data_dir())),
                    "text": text.strip(),
                    "duration": sf.info(flac).duration,
                }
            )
    return pd.DataFrame(rows)


def load_index(rebuild: bool = False) -> pd.DataFrame:
    path = index_path()
    if path.exists() and not rebuild:
        return pd.read_parquet(path)
    df = build_index()
    df.to_parquet(path, index=False)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true", help="ignore the parquet cache")
    df = load_index(rebuild=parser.parse_args().rebuild)
    print(
        f"{len(df)} utterances, {df.speaker_id.nunique()} speakers, "
        f"{df.duration.sum() / 3600:.2f} h -> {index_path()}"
    )


if __name__ == "__main__":
    main()
