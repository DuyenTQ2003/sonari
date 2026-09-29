"""Build the G0 spike pair from LibriSpeech dev-clean, by script (no recording).

good.wav: a word with initial /θ/ (think, three, thank, thought) plus ~0.3 s context.
bad.wav:  a word with initial /t/ (tin, took, talk, time) plus ~0.3 s context,
          from the same speaker when one has both.

LibriSpeech has no word timings, so word boundaries come from forced alignment of the
known transcript with a character CTC model (ALIGNER). That model is independent of the
phoneme model under test and never sees the target phonemes; it only places the words.
"""

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
import soundfile as sf
import torch
from common import data_dir
from ctc_align import token_spans, viterbi_align
from index import load_index
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

# Priority order. THOUGHT is last: its final /t/ would inflate the t posterior in good.wav.
THETA_WORDS = ("THINK", "THREE", "THANK", "THOUGHT")
T_WORDS = ("TIN", "TOOK", "TALK", "TIME")
CONTEXT_S = 0.3
SAMPLE_RATE = 16000
ALIGNER = "facebook/wav2vec2-base-960h"
FRAME_S = 320 / SAMPLE_RATE  # wav2vec2 frame stride
SELECTION_RULE = (
    "same speaker first; then prefer occurrences whose neighbouring transcript words do "
    "not put the contrast sound at the word edge (for /θ/ clips: no neighbour ending in T "
    "or starting with T; for /t/ clips: no neighbour starting or ending with TH); then word "
    "priority order; then shorter utterance; then speaker id and utterance id"
)


@dataclass
class Occurrence:
    utterance_id: str
    speaker_id: str
    word: str
    word_index: int
    clean_context: bool
    priority: int
    duration: float

    def key(self) -> tuple[bool, int, float, str]:
        return (not self.clean_context, self.priority, self.duration, self.utterance_id)


def clean_neighbours(words: list[str], i: int, contrast: str) -> bool:
    """True when neither neighbour of words[i] puts the contrast sound at its edge."""
    prev = words[i - 1] if i > 0 else ""
    nxt = words[i + 1] if i + 1 < len(words) else ""
    if contrast == "T":  # avoid a /t/ right next to the /θ/ word
        return not prev.endswith("T") and not (nxt.startswith("T") and not nxt.startswith("TH"))
    return not prev.endswith("TH") and not nxt.startswith("TH")


def occurrences(df: pd.DataFrame, targets: tuple[str, ...], contrast: str) -> list[Occurrence]:
    found = []
    for row in df.itertuples():
        words = row.text.split()
        for priority, target in enumerate(targets):
            if target in words:
                i = words.index(target)
                found.append(
                    Occurrence(
                        row.utterance_id,
                        row.speaker_id,
                        target,
                        i,
                        clean_neighbours(words, i, contrast),
                        priority,
                        row.duration,
                    )
                )
                break
    return found


def choose_pair(df: pd.DataFrame) -> tuple[Occurrence, Occurrence, bool]:
    good = occurrences(df, THETA_WORDS, contrast="T")
    bad = occurrences(df, T_WORDS, contrast="TH")
    if not good or not bad:
        raise SystemExit("no /θ/ or no /t/ candidate in the index")
    best_pairs = []
    for speaker in sorted({o.speaker_id for o in good} & {o.speaker_id for o in bad}):
        g = min((o for o in good if o.speaker_id == speaker), key=Occurrence.key)
        b = min((o for o in bad if o.speaker_id == speaker), key=Occurrence.key)
        best_pairs.append(((g.key()[:2], b.key()[:2], speaker), g, b))
    if best_pairs:
        _, g, b = min(best_pairs, key=lambda p: p[0])
        return g, b, True
    return min(good, key=Occurrence.key), min(bad, key=Occurrence.key), False


class WordAligner:
    def __init__(self) -> None:
        self.processor = Wav2Vec2Processor.from_pretrained(ALIGNER)
        self.model = Wav2Vec2ForCTC.from_pretrained(ALIGNER).eval()
        self.vocab = self.processor.tokenizer.get_vocab()
        self.blank = self.processor.tokenizer.pad_token_id

    def word_spans(self, audio: np.ndarray, text: str) -> list[tuple[float, float]]:
        """(start_s, end_s) of every word in text, by forced alignment."""
        words = text.split()
        targets, owner = [], []
        for w, word in enumerate(words):
            if w:
                targets.append(self.vocab["|"])
                owner.append(-1)
            for ch in word:
                targets.append(self.vocab[ch])
                owner.append(w)
        inputs = self.processor(audio, sampling_rate=SAMPLE_RATE, return_tensors="pt")
        with torch.inference_mode():
            logits = self.model(inputs.input_values).logits[0]
        log_probs = torch.log_softmax(logits, dim=-1).numpy()
        spans = token_spans(viterbi_align(log_probs, targets, self.blank), len(targets))
        result = []
        for w in range(len(words)):
            mine = [s for s, o in zip(spans, owner, strict=True) if o == w]
            result.append((mine[0][0] * FRAME_S, mine[-1][1] * FRAME_S))
        return result


def load_audio(path: str) -> np.ndarray:
    audio, sr = sf.read(data_dir() / path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != SAMPLE_RATE:
        raise SystemExit(f"{path}: expected {SAMPLE_RATE} Hz, got {sr}")
    return audio


def cut_clip(
    df: pd.DataFrame, occ: Occurrence, aligner: WordAligner, name: str, expected: str
) -> dict:
    row = df.set_index("utterance_id").loc[occ.utterance_id]
    audio = load_audio(row.flac_path)
    words = row.text.split()
    spans = aligner.word_spans(audio, row.text)
    word_start, word_end = spans[occ.word_index]
    total = len(audio) / SAMPLE_RATE
    clip_start = max(0.0, word_start - CONTEXT_S)
    clip_end = min(total, word_end + CONTEXT_S)
    clip = audio[round(clip_start * SAMPLE_RATE) : round(clip_end * SAMPLE_RATE)]
    out = data_dir() / "derived" / "g0" / f"{name}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, clip, SAMPLE_RATE, subtype="PCM_16")
    context = [w for w, (s, e) in zip(words, spans, strict=True) if e > clip_start and s < clip_end]
    return {
        "file": str(out.relative_to(data_dir())),
        "expected_initial_phoneme": expected,
        "word": occ.word.lower(),
        "utterance_id": occ.utterance_id,
        "speaker_id": occ.speaker_id,
        "chapter_id": str(row.chapter_id),
        "source_flac": row.flac_path,
        "transcript": row.text,
        "word_index": occ.word_index,
        "clean_context": occ.clean_context,
        "source_word_start_s": round(word_start, 3),
        "source_word_end_s": round(word_end, 3),
        "clip_start_s": round(clip_start, 3),
        "clip_end_s": round(clip_end, 3),
        "word_start_in_clip_s": round(word_start - clip_start, 3),
        "word_end_in_clip_s": round(word_end - clip_start, 3),
        "clip_duration_s": round(len(clip) / SAMPLE_RATE, 3),
        "words_in_clip": [w.lower() for w in context],
    }


def main() -> None:
    df = load_index()
    good, bad, same_speaker = choose_pair(df)
    aligner = WordAligner()
    manifest = {
        "gate": "G0",
        "dataset": "LibriSpeech dev-clean (OpenSLR SLR12), CC BY 4.0",
        "attribution": "Panayotov et al., ICASSP 2015; audio from LibriVox",
        "sample_rate": SAMPLE_RATE,
        "context_s": CONTEXT_S,
        "word_aligner": ALIGNER,
        "same_speaker": same_speaker,
        "selection_rule": SELECTION_RULE,
        "good": cut_clip(df, good, aligner, "good", "θ"),
        "bad": cut_clip(df, bad, aligner, "bad", "t"),
    }
    path = data_dir() / "derived" / "g0" / "g0_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for name in ("good", "bad"):
        clip = manifest[name]
        print(
            f"{name}: '{clip['word']}' from {clip['utterance_id']} (speaker {clip['speaker_id']})"
            f", {clip['clip_duration_s']} s, words: {' '.join(clip['words_in_clip'])}"
        )
    print(f"same speaker: {same_speaker}; manifest -> {path}")


if __name__ == "__main__":
    main()
