# P01 spike results: wav2vec2 espeak on the G0 pair

Date: 2026-09-29. Model: `facebook/wav2vec2-lv-60-espeak-cv-ft` (torch 2.14 CPU,
transformers 5.17). Greedy CTC decode, no language model.

## Verdict

- `good.wav` ("think", expect /θ/): **decodes θ.** PASS.
- `bad.wav` ("took", expect /t/): **decodes t.** PASS.
- The two word decodes differ (`θ ɪ ŋ` vs `d t ʊ`). The model separates the two sounds
  on this pair. This is one pair from one native speaker: it shows the signal exists,
  not that GOP works. That is P02's job.

## Reproduce

```bash
uv run python tools/evaldata/fetch_librispeech.py   # dev-clean, md5-checked
uv run python tools/evaldata/index.py                # 2703 utterances, 40 speakers
uv run python tools/evaldata/build_g0.py             # DATA_DIR/derived/g0/
uv run --directory spikes/gop python run_spike.py
```

## Decodes

| Clip | Words in clip | Clip decode | Word-window decode |
|---|---|---|---|
| good | one **think** you | `ʌ n θ ɪ ŋ k uː` | `θ ɪ ŋ` (frames 12–24) |
| bad | and **took** his dead | `æ n d t ʊ k h ɪ z` | `d t ʊ` (frames 12–23) |

## Posteriors

Softmax probability per 20 ms frame. "Word window" = aligned word span from the
manifest, start padded by 0.05 s.

| Clip | Token | Clip max | Clip top-5 mean | Window max | Window top-5 mean |
|---|---|---|---|---|---|
| good | θ | 0.9369 | 0.1875 | 0.9369 | 0.1875 |
| good | t | 0.0031 | 0.0017 | 0.0031 | 0.0011 |
| bad | θ | 0.0002 | 0.0001 | 0.0002 | 0.0001 |
| bad | t | 0.9603 | 0.2344 | 0.9603 | 0.2051 |

Max P(θ) is 0.94 vs 0.0002; max P(t) is 0.96 vs 0.003. Both gaps are over two orders
of magnitude.

## Caveats (read before P02)

- **CTC posteriors are spiky.** Each phoneme peaks in about one frame and the other
  frames go to blank, so the top-5 mean (~0.19–0.23) mostly measures blank frames. It is
  a poor score. GOP in P02 should score the frames that forced alignment assigns to the
  phoneme, not a fixed top-k.
- **Word windows are tight.** Boundaries come from a character CTC aligner
  (`facebook/wav2vec2-base-960h`), whose spikes fall inside the word, so the window cut
  the final /k/ of "think"; the 0.05 s start pad took in the /d/ of "and" before
  "took". The 0.3 s context around each clip covers the whole word.
- **n = 1, native speaker, clean read speech.** No claim about learners or accents
  (see `docs/eval-data.md`, honesty rules).
- The θ token never fired in `bad.wav` and t never fired in `good.wav`, so this pair has
  no cross-talk from context words. Selection preferred neighbours without an edge /t/
  or /θ/ for this reason, and avoided "thought" (final /t/).

## Manifest (`DATA_DIR/derived/g0/g0_manifest.json`)

```json
{
  "gate": "G0",
  "dataset": "LibriSpeech dev-clean (OpenSLR SLR12), CC BY 4.0",
  "attribution": "Panayotov et al., ICASSP 2015; audio from LibriVox",
  "sample_rate": 16000,
  "context_s": 0.3,
  "word_aligner": "facebook/wav2vec2-base-960h",
  "same_speaker": true,
  "selection_rule": "same speaker first; then prefer occurrences whose neighbouring transcript words do not put the contrast sound at the word edge (for /θ/ clips: no neighbour ending in T or starting with T; for /t/ clips: no neighbour starting or ending with TH); then word priority order; then shorter utterance; then speaker id and utterance id",
  "good": {
    "file": "derived/g0/good.wav",
    "expected_initial_phoneme": "θ",
    "word": "think",
    "utterance_id": "1993-147149-0008",
    "speaker_id": "1993",
    "chapter_id": "147149",
    "source_flac": "librispeech/dev-clean/1993/147149/1993-147149-0008.flac",
    "transcript": "IS THERE ANY CHANCE FOR THE OTHER ONE THINK YOU",
    "word_index": 8,
    "clean_context": true,
    "source_word_start_s": 2.4,
    "source_word_end_s": 2.58,
    "clip_start_s": 2.1,
    "clip_end_s": 2.88,
    "word_start_in_clip_s": 0.3,
    "word_end_in_clip_s": 0.48,
    "clip_duration_s": 0.78,
    "words_in_clip": [
      "one",
      "think",
      "you"
    ]
  },
  "bad": {
    "file": "derived/g0/bad.wav",
    "expected_initial_phoneme": "t",
    "word": "took",
    "utterance_id": "1993-147149-0009",
    "speaker_id": "1993",
    "chapter_id": "147149",
    "source_flac": "librispeech/dev-clean/1993/147149/1993-147149-0009.flac",
    "transcript": "BUT EARNEST AS THE FATHER WAS IN WATCHING THE YET LIVING HE HAD EYES AND EARS FOR ALL THAT CONCERNED THE DEAD AND SPRANG GENTLY UP AND TOOK HIS DEAD SON ON HIS HARD COUCH IN HIS ARMS WITH TENDER STRENGTH AND CARRIED HIM UPSTAIRS AS IF AFRAID OF WAKENING HIM",
    "word_index": 27,
    "clean_context": true,
    "source_word_start_s": 8.94,
    "source_word_end_s": 9.1,
    "clip_start_s": 8.64,
    "clip_end_s": 9.4,
    "word_start_in_clip_s": 0.3,
    "word_end_in_clip_s": 0.46,
    "clip_duration_s": 0.76,
    "words_in_clip": [
      "and",
      "took",
      "his",
      "dead"
    ]
  }
}
```

Audio: LibriSpeech dev-clean, CC BY 4.0 (Panayotov et al., ICASSP 2015; LibriVox).
No audio is committed.
