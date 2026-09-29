"""P01 spike: does wav2vec2-lv-60-espeak separate /θ/ from /t/ on the G0 pair?

For good.wav and bad.wav: greedy CTC decode, then frame posteriors of the θ and t
tokens (max over frames, mean of the top-5 frames), over the whole clip and over the
target-word window from the manifest (padded by WINDOW_PAD_S at the start only, so the
word onset is covered without reaching far into the previous word).
"""

import json
import os
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from huggingface_hub import hf_hub_download
from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForCTC

MODEL = "facebook/wav2vec2-lv-60-espeak-cv-ft"
TOKENS = ("θ", "t")
TOP_K = 5
FRAME_S = 320 / 16000
WINDOW_PAD_S = 0.05


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "~/sonari-data")).expanduser()


def greedy(ids: np.ndarray, id2tok: dict[int, str], blank: int) -> list[str]:
    out, prev = [], None
    for i in ids:
        if i != prev and i != blank:
            out.append(id2tok[int(i)])
        prev = i
    return out


def stats(p: np.ndarray) -> dict[str, float]:
    top = np.sort(p)[-TOP_K:]
    return {"max": round(float(p.max()), 4), "top5_mean": round(float(top.mean()), 4)}


def run_clip(clip: dict, model, extractor, vocab: dict[str, int], blank: int) -> dict:
    audio, sr = sf.read(data_dir() / clip["file"], dtype="float32")
    assert sr == 16000 and audio.ndim == 1
    inputs = extractor(audio, sampling_rate=sr, return_tensors="pt")
    with torch.inference_mode():
        logits = model(inputs.input_values).logits[0]
    probs = torch.softmax(logits, dim=-1).numpy()
    ids = probs.argmax(axis=-1)
    id2tok = {v: k for k, v in vocab.items()}
    lo = max(0, int((clip["word_start_in_clip_s"] - WINDOW_PAD_S) / FRAME_S))
    hi = min(len(ids), int(np.ceil(clip["word_end_in_clip_s"] / FRAME_S)))
    word_decode = greedy(ids[lo:hi], id2tok, blank)
    expected = clip["expected_initial_phoneme"]
    first = next((t for t in word_decode if t in TOKENS), None)
    return {
        "word": clip["word"],
        "expected": expected,
        "clip_decode": " ".join(greedy(ids, id2tok, blank)),
        "word_window_frames": [lo, hi],
        "word_decode": " ".join(word_decode),
        "first_theta_or_t_in_word": first,
        "decodes_expected": first == expected,
        "clip": {tok: stats(probs[:, vocab[tok]]) for tok in TOKENS},
        "word_window": {tok: stats(probs[lo:hi, vocab[tok]]) for tok in TOKENS},
    }


def main() -> None:
    manifest = json.loads((data_dir() / "derived/g0/g0_manifest.json").read_text("utf-8"))
    extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL)
    model = Wav2Vec2ForCTC.from_pretrained(MODEL).eval()
    vocab = json.loads(Path(hf_hub_download(MODEL, "vocab.json")).read_text("utf-8"))
    blank = model.config.pad_token_id
    results = {n: run_clip(manifest[n], model, extractor, vocab, blank) for n in ("good", "bad")}
    for name, r in results.items():
        verdict = "PASS" if r["decodes_expected"] else "FAIL"
        print(f"== {name}.wav ('{r['word']}', expect /{r['expected']}/): {verdict}")
        print(f"  clip decode : {r['clip_decode']}")
        print(f"  word decode : {r['word_decode']}  (frames {r['word_window_frames']})")
        for scope in ("clip", "word_window"):
            for tok in TOKENS:
                s = r[scope][tok]
                print(f"  P({tok}) {scope:<11} max={s['max']:.4f} top5_mean={s['top5_mean']:.4f}")
    same = results["good"]["word_decode"] == results["bad"]["word_decode"]
    print(f"both word decodes identical: {same}")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
