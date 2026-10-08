"""Score a fixed-seed sample of LibriSpeech dev-clean against its transcripts.

    make score-native ARGS="--n 400 --workers 4"

Writes one JSON line per utterance to DATA_DIR/derived/score_eval/native-<seed>-<n>.jsonl
(LibriSpeech is CC BY 4.0; the file stays outside the repo like all data). Only utterances
the service would accept are drawn: at most `Settings().max_clip_s` (15 s).
"""

import argparse
import asyncio
import json
import os
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

SEED = 20261008


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "~/sonari-data")).expanduser()


def sample(index: list[dict[str, Any]], n: int, max_s: float, seed: int) -> list[dict[str, Any]]:
    """`n` utterances of at most `max_s` seconds, by a seeded draw over the sorted index."""
    fit = sorted((r for r in index if r["duration"] <= max_s), key=lambda r: r["utterance_id"])
    return random.Random(seed).sample(fit, n)


def _shard(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from score_eval.score import ClipScorer, to_wav

    async def run() -> list[dict[str, Any]]:
        scorer = ClipScorer()
        await scorer.start()
        out = []
        for r in rows:
            audio = to_wav(str(data_dir() / r["flac_path"]))
            try:
                scored = await scorer.score(audio, r["text"])
            except Exception as err:  # reported, not hidden: the report counts them
                scored = {"error": f"{type(err).__name__}: {err}"}
            meta = {"id": r["utterance_id"], "speaker": r["speaker_id"], "text": r["text"]}
            out.append(meta | scored)
        return out

    return asyncio.run(run())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=400)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    import pyarrow.parquet as pq
    from sonari_speech.settings import Settings

    index = pq.read_table(data_dir() / "librispeech" / "dev-clean.index.parquet").to_pylist()
    rows = sample(index, args.n, Settings().max_clip_s, args.seed)
    shards = [rows[i :: args.workers] for i in range(args.workers)]
    with ProcessPoolExecutor(args.workers) as pool:
        results = [r for shard in pool.map(_shard, shards) for r in shard]
    results.sort(key=lambda r: r["id"])
    out = data_dir() / "derived" / "score_eval" / f"native-{args.seed}-{args.n}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results), "utf-8")
    print(f"{len(results)} utterances, {sum('error' in r for r in results)} errors -> {out}")


if __name__ == "__main__":
    main()
