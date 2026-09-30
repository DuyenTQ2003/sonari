"""P05 spike: generate course-style audio with Kokoro-82M and measure real-time factor.

Writes, under DATA_DIR/derived/tts (never in the repo):
  sentence_{0.80,1.00,1.15}x.wav   one VOA sentence at three speeds
  dialogue_NN_<speaker>.wav        the six turns of a VOA dialogue, one file per turn
  dialogue_6turn.wav               the turns joined with a short gap
and spikes/tts/RESULTS.md with the RTF table. It does not judge quality: that is
CHECKLIST.md, filled in by ear.

Usage: uv run --directory spikes/tts python run_tts.py
"""

import json
import os
import platform
import statistics
import time
from importlib.metadata import version
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from huggingface_hub import hf_hub_download
from kokoro import KPipeline

HERE = Path(__file__).parent
REPO_ID = "hexgrad/Kokoro-82M"
SAMPLE_RATE = 24000
THREADS = (1, 2, 4)
WAV_THREADS = 4
RUNS = 5


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "~/sonari-data")).expanduser()


def synth(pipeline: KPipeline, text: str, voice: str, speed: float) -> np.ndarray:
    """One utterance as float32 mono at 24 kHz (chunks joined; a short text is one chunk)."""
    chunks = [audio.numpy() for _, _, audio in pipeline(text, voice=voice, speed=speed)]
    return np.concatenate(chunks).astype(np.float32)


def seconds(audio: np.ndarray) -> float:
    return len(audio) / SAMPLE_RATE


def join_turns(turns: list[np.ndarray], gap_s: float) -> np.ndarray:
    gap = np.zeros(round(gap_s * SAMPLE_RATE), dtype=np.float32)
    parts: list[np.ndarray] = []
    for turn in turns:
        parts += [turn, gap]
    return np.concatenate(parts[:-1])


def rtf_runs(jobs: list[tuple[str, str, float]], pipeline: KPipeline) -> list[float]:
    """RTF of RUNS passes over jobs (text, voice, speed): synthesis time / audio time."""
    out = []
    for _ in range(RUNS):
        start = time.perf_counter()
        audio_s = sum(seconds(synth(pipeline, *job)) for job in jobs)
        out.append((time.perf_counter() - start) / audio_s)
    return out


def cpu_model() -> str:
    for line in Path("/proc/cpuinfo").read_text("utf-8").splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown"


def write_wav(path: Path, audio: np.ndarray) -> None:
    sf.write(path, audio, SAMPLE_RATE, subtype="PCM_16")


def main() -> None:
    texts = json.loads((HERE / "texts.json").read_text("utf-8"))
    sentence, dialogue = texts["sentence"], texts["dialogue"]
    out = data_dir() / "derived" / "tts"
    out.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    pipeline = KPipeline(lang_code="a", repo_id=REPO_ID)
    load_s = time.perf_counter() - start
    revision = Path(hf_hub_download(REPO_ID, "config.json")).parent.name
    torch.set_num_threads(WAV_THREADS)
    synth(pipeline, "Warm up.", sentence["voice"], 1.0)

    files: list[tuple[str, float]] = []
    for speed in sentence["speeds"]:
        audio = synth(pipeline, sentence["text"], sentence["voice"], speed)
        name = f"sentence_{speed:.2f}x.wav"
        write_wav(out / name, audio)
        files.append((name, seconds(audio)))

    turn_audio = []
    for n, turn in enumerate(dialogue["turns"], start=1):
        voice = dialogue["voices"][turn["speaker"]]
        audio = synth(pipeline, turn["text"], voice, 1.0)
        turn_audio.append(audio)
        name = f"dialogue_{n:02d}_{turn['speaker']}.wav"
        write_wav(out / name, audio)
        files.append((name, seconds(audio)))
    joined = join_turns(turn_audio, dialogue["gap_s"])
    write_wav(out / "dialogue_6turn.wav", joined)
    files.append(("dialogue_6turn.wav", seconds(joined)))

    cases = {
        f"sentence {speed:.2f}x": [(sentence["text"], sentence["voice"], speed)]
        for speed in sentence["speeds"]
    } | {
        "dialogue, 6 turns": [
            (t["text"], dialogue["voices"][t["speaker"]], 1.0) for t in dialogue["turns"]
        ]
    }
    rtf: dict[str, dict[int, list[float]]] = {name: {} for name in cases}
    for threads in THREADS:
        torch.set_num_threads(threads)
        for name, jobs in cases.items():
            rtf[name][threads] = rtf_runs(jobs, pipeline)

    (HERE / "RESULTS.md").write_text(
        render(files, rtf, load_s, revision, str(out)), encoding="utf-8"
    )
    print(f"wrote {len(files)} wavs to {out} and {HERE / 'RESULTS.md'}")


def render(
    files: list[tuple[str, float]],
    rtf: dict[str, dict[int, list[float]]],
    load_s: float,
    revision: str,
    out: str,
) -> str:
    head = "| Case | " + " | ".join(f"{t} thread{'s' if t > 1 else ''}" for t in THREADS) + " |"
    rows = [head, "|---|" + "---|" * len(THREADS)]
    for name, by_threads in rtf.items():
        cells = [
            f"{statistics.median(by_threads[t]):.3f} (max {max(by_threads[t]):.3f})"
            for t in THREADS
        ]
        rows.append(f"| {name} | " + " | ".join(cells) + " |")
    durations = ["| File | Audio (s) |", "|---|---|"]
    durations += [f"| `{name}` | {dur:.2f} |" for name, dur in files]
    return f"""# P05 results: Kokoro-82M on CPU

Generated by `run_tts.py`; do not edit by hand. This file records measurements only.
Quality is judged by ear in `CHECKLIST.md`.

- Model: `{REPO_ID}` revision `{revision}`, `kokoro` {version("kokoro")}, torch
  {torch.__version__}, 24 kHz mono.
- CPU: {cpu_model()} ({os.cpu_count()} logical cores, {platform.platform()}).
- Pipeline load (weights already cached): {load_s:.1f} s.
- Sentence voice `af_heart`; dialogue voices `af_heart` (Anna) and `am_michael` (Jonathan).
- Audio is written to `{out}`, outside the repo.

## Real-time factor

RTF = synthesis wall time / audio duration, so lower is faster and 1.0 is real time.
Median of {RUNS} passes after a warm-up, with the number of intra-op torch threads shown
(max of the {RUNS} passes in brackets). The dialogue row synthesises all six turns per
pass and divides by the speech duration, gaps excluded.

{chr(10).join(rows)}

This machine is a WSL2 guest, not the target VPS. P04 measures the VPS; treat these
numbers as a feasibility check only. Course audio is generated offline in the worker, so
RTF sets batch time, not learner latency.

## Files

{chr(10).join(durations)}
"""


if __name__ == "__main__":
    main()
