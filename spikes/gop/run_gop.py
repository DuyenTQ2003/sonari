"""P02 spike (HARD GATE G0): CTC forced alignment + naive GOP on the G0 pair.

Each clip is aligned to the target word's espeak IPA over the whole clip; context
words fall into the leading/trailing blank states. For every aligned segment:

    gop = mean over frames of (log p(expected) - max_{q != expected} log p(q))

q ranges over phoneme tokens only: blank and special tokens (<pad>, <s>, </s>, <unk>)
are excluded, so the competitor is always a phoneme. The blank-inclusive variant is
reported alongside, never used for the verdict. Both choices were fixed before the
first run.

Gate (fixed before the first run): on good.wav, the /θ/ segment scores gop > 0 against
the correct reference, the /t/ segment scores gop < 0 against the substituted reference
(θ -> t), and the substituted case names θ as competitor.
"""

import json
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from huggingface_hub import hf_hub_download
from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForCTC

from align import token_spans, viterbi_align
from run_spike import FRAME_S, MODEL, data_dir

SAMPLE_RATE = 16000
SPECIAL = ("<s>", "<pad>", "</s>", "<unk>")
# espeak IPA per G0 word, spelled as tokens of the model vocab (checked at startup).
LEXICON = {
    "think": ["θ", "ɪ", "ŋ", "k"],
    "three": ["θ", "ɹ", "iː"],
    "thank": ["θ", "æ", "ŋ", "k"],
    "thought": ["θ", "ɔː", "t"],
    "tin": ["t", "ɪ", "n"],
    "took": ["t", "ʊ", "k"],
    "talk": ["t", "ɔː", "k"],
    "time": ["t", "aɪ", "m"],
}
SUBSTITUTE = {"θ": "t", "t": "θ"}


class Scorer:
    def __init__(self) -> None:
        self.extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL)
        self.model = Wav2Vec2ForCTC.from_pretrained(MODEL).eval()
        vocab_path = Path(hf_hub_download(MODEL, "vocab.json"))
        self.vocab: dict[str, int] = json.loads(vocab_path.read_text("utf-8"))
        self.id2tok = {v: k for k, v in self.vocab.items()}
        self.blank = self.model.config.pad_token_id
        self.phoneme_ids = np.array(sorted(v for k, v in self.vocab.items() if k not in SPECIAL))

    def log_probs(self, audio: np.ndarray) -> np.ndarray:
        inputs = self.extractor(audio, sampling_rate=SAMPLE_RATE, return_tensors="pt")
        with torch.inference_mode():
            logits = self.model(inputs.input_values).logits[0]
        return torch.log_softmax(logits, dim=-1).numpy()

    def score(self, log_probs: np.ndarray, phones: list[str]) -> list[dict]:
        missing = [p for p in phones if p not in self.vocab]
        if missing:
            raise SystemExit(f"tokens not in model vocab: {missing}")
        ids = [self.vocab[p] for p in phones]
        spans = token_spans(viterbi_align(log_probs, ids, self.blank), len(ids))
        segments = []
        for idx, (phone, tid, (start, end)) in enumerate(zip(phones, ids, spans, strict=True)):
            seg = log_probs[start:end]
            others = self.phoneme_ids[self.phoneme_ids != tid]
            best_other = seg[:, others].max(axis=1)
            with_blank = np.maximum(best_other, seg[:, self.blank])
            competitor = int(others[seg[:, others].mean(axis=0).argmax()])
            segments.append(
                {
                    "idx": idx,
                    "phone": phone,
                    "start_ms": round(start * FRAME_S * 1000),
                    "end_ms": round(end * FRAME_S * 1000),
                    "frames": end - start,
                    "gop": round(float(np.mean(seg[:, tid] - best_other)), 3),
                    "gop_incl_blank": round(float(np.mean(seg[:, tid] - with_blank)), 3),
                    "competitor": self.id2tok[competitor],
                    "p_expected": round(float(np.exp(seg[:, tid]).mean()), 4),
                }
            )
        return segments


def export_segments(audio: np.ndarray, name: str, segments: list[dict]) -> None:
    """Write each aligned segment as its own wav under DATA_DIR (never in the repo)."""
    out = data_dir() / "derived" / "g0" / "segments"
    out.mkdir(parents=True, exist_ok=True)
    for s in segments:
        lo, hi = (round(ms * SAMPLE_RATE / 1000) for ms in (s["start_ms"], s["end_ms"]))
        sf.write(out / f"{name}_{s['idx']}_{s['phone']}.wav", audio[lo:hi], SAMPLE_RATE)


def main() -> None:
    manifest = json.loads((data_dir() / "derived/g0/g0_manifest.json").read_text("utf-8"))
    scorer = Scorer()
    runs = {}
    for clip_name in ("good", "bad"):
        clip = manifest[clip_name]
        audio, sr = sf.read(data_dir() / clip["file"], dtype="float32")
        assert sr == SAMPLE_RATE and audio.ndim == 1
        log_probs = scorer.log_probs(audio)
        correct = LEXICON[clip["word"]]
        substituted = [SUBSTITUTE[correct[0]], *correct[1:]]
        for ref_name, phones in (("correct", correct), ("substituted", substituted)):
            name = f"{clip_name}-{ref_name}"
            segments = scorer.score(log_probs, phones)
            export_segments(audio, name, segments)
            runs[name] = {
                "word": clip["word"],
                "reference": " ".join(phones),
                "manifest_word_ms": [
                    round(clip["word_start_in_clip_s"] * 1000),
                    round(clip["word_end_in_clip_s"] * 1000),
                ],
                "segments": segments,
            }

    for name, run in runs.items():
        print(
            f"== {name}: '{run['word']}' scored as /{run['reference']}/ "
            f"(manifest word span {run['manifest_word_ms']} ms)"
        )
        for s in run["segments"]:
            print(
                f"  {s['idx']} {s['phone']:<3} {s['start_ms']:>4}-{s['end_ms']:<4} ms "
                f"gop={s['gop']:>8.3f} (incl blank {s['gop_incl_blank']:>8.3f}) "
                f"competitor={s['competitor']} p={s['p_expected']}"
            )

    good_ok = runs["good-correct"]["segments"][0]
    good_sub = runs["good-substituted"]["segments"][0]
    passed = good_ok["gop"] > 0 > good_sub["gop"] and good_sub["competitor"] == "θ"
    print(
        f"GATE G0: {'PASS' if passed else 'FAIL'} "
        f"(θ|correct gop={good_ok['gop']}, t|substituted gop={good_sub['gop']}, "
        f"competitor={good_sub['competitor']})"
    )
    print(json.dumps(runs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
