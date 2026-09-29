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

---

# P02 results: forced alignment + naive GOP (HARD GATE G0)

Date: 2026-09-29. Aligner: `spikes/gop/align.py` (numpy CTC Viterbi, no torchaudio).
Script: `uv run --directory spikes/gop python run_gop.py`.

Method, fixed before the first run:
- Each clip is aligned over its whole length to the target word's espeak IPA; the
  context words fall into the leading and trailing blank states.
- `gop = mean over segment frames of (log p(expected) - max_{q != expected} log p(q))`,
  with q over phoneme tokens only (blank and `<s> <pad> </s> <unk>` excluded). The
  blank-inclusive value is shown for reference and is not used for the verdict.
- Competitor = the phoneme token with the highest mean log posterior over the segment.
- Gate: on good.wav, gop(θ | correct) > 0, gop(t | substituted θ→t) < 0, and the
  substituted case names θ as competitor.

## Verdict: PASS

On good.wav ("think"), /θ/ against the correct reference scores **gop = +3.886**;
/t/ against the substituted reference scores **gop = −5.713**, and the named
competitor is **θ**, the phoneme the speaker actually produced. That is a gap of
9.6 nats on the same audio and the same frames (300–320 ms).

## Segments

Boundaries are in ms from the clip start. A segment is the frames the CTC path assigns
to the token, so most are one 20 ms frame. Manifest word spans (from the P01 character
aligner): good "think" 300–480 ms, bad "took" 300–460 ms.

| Run | Reference | # | Phone | ms | gop | gop incl. blank | Competitor | mean p |
|---|---|---|---|---|---|---|---|---|
| good | correct | 0 | θ | 300–320 | 3.886 | 3.886 | ð | 0.9369 |
| good | correct | 1 | ɪ | 360–380 | 2.974 | 2.974 | i | 0.8610 |
| good | correct | 2 | ŋ | 440–460 | 1.575 | 1.575 | n | 0.8110 |
| good | correct | 3 | k | 520–540 | 3.353 | 3.353 | kʲ | 0.8988 |
| good | substituted | 0 | **t** | 300–320 | **−5.713** | −5.713 | **θ** | 0.0031 |
| good | substituted | 1 | ɪ | 360–380 | 2.974 | 2.974 | i | 0.8610 |
| good | substituted | 2 | ŋ | 440–460 | 1.575 | 1.575 | n | 0.8110 |
| good | substituted | 3 | k | 520–540 | 3.353 | 3.353 | kʲ | 0.8988 |
| bad | correct | 0 | t | 280–300 | 3.798 | 3.798 | d | 0.9603 |
| bad | correct | 1 | ʊ | 360–380 | 1.350 | 1.350 | ə | 0.5182 |
| bad | correct | 2 | k | 460–500 | 4.464 | 1.940 | ɡ | 0.7771 |
| bad | substituted | 0 | **θ** | **160–180** | −10.047 | −10.047 | **æ** | 0.0000 |
| bad | substituted | 1 | ʊ | 360–380 | 1.350 | 1.350 | ə | 0.5182 |
| bad | substituted | 2 | k | 460–500 | 4.464 | 1.940 | ɡ | 0.7771 |

Segment wavs: `DATA_DIR/derived/g0/segments/<run>_<idx>_<phone>.wav` (14 files, kept
out of the repo like all audio). At 20–40 ms each they are too short to judge by ear;
placement was checked against the manifest word spans instead.

## Findings

- **Placement.** In good.wav every segment sits in order inside or just after the
  manifest span; /k/ at 520–540 ms is past the manifest end (480 ms), which confirms
  the P01 note that the character aligner cut the final /k/.
- **The symmetric case misplaces the missing phoneme (not gating, but it matters for
  G1).** Scoring bad.wav ("took") against /θ ʊ k/, the aligner put /θ/ at 160–180 ms,
  inside the preceding word "and", not at the /t/ onset (280–300 ms). The competitor is
  therefore `æ`, not `t`. The low gop (−10.0) would still flag an error, but it names
  the wrong sound and points at the wrong place. In good.wav the substituted /t/ landed
  on the right frame only because no better spot existed nearby. Cause: whole-clip
  alignment lets an absent phoneme drift into context, since the leading blank state
  can absorb any frames. G1 must constrain the search (align the full context
  sequence, or restrict to the word span) before its competitor names can be trusted.
- The blank-inclusive GOP differs only on the /k/ of "took" (a two-frame segment whose
  second frame is mostly blank), which is why it is not the primary score.
- n = 1 pair, native speaker, one contrast. This passes the go/no-go gate; it is not a
  calibration. Thresholds come from G1.
