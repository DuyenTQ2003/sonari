# /v1/score false alarms on a Vietnamese speaker: what changed, what it costs, what to expect

Date: 2026-10-08. Branch `fix/score-false-alarms`. Thresholds `v1-native-g0`.

## The evidence

One recording, one Vietnamese speaker reading "Poor parsley, valued for its looks, then thrown
away." normally: 17 of 32 phonemes wrong, all 9 words wrong (thresholds v0, `gop > 0`). The owner
read the response and named three causes of false alarms:

1. The reference is American and rhotic (ɔːɹ in "for", ʊɹ in "Poor", ɑːɹ in "parsley"); a
   non-rhotic reading is correct, and IELTS accepts both.
2. Threshold 0 has no margin: near pairs fail on a small negative GOP (i/iː −0.19, ə/ɐ −1.06,
   ɔːɹ −0.20, t −0.65).
3. Alignment drift: implausible "heard" values (l heard as s at −9.1 and j as t in "valued",
   n as v in "thrown").

Errors that look real and must survive: p heard as b twice (unaspirated /p/, a known
Vietnamese feature), final /s/ lost in "looks", θ heard as d.

## What changed

| Cause | Change | Where |
|---|---|---|
| 1 | Every sentence is scored against en-us (g2p_en, as before) **and** en-gb (espeak-ng 1.52, citation forms). Each word keeps the reference with fewer wrong, then fewer unclear, then the higher mean GOP; a tie keeps en-us. The response says which (`reference`). | `g2p/espeak.py`, `scoring/accents.py` |
| 2 | Three verdicts: `correct` (gop > 0), `unclear` (−3.4 ≤ gop ≤ 0), `wrong` (gop < −3.4). Only `wrong` carries a feedback key. Contract first: `packages/contracts/schema/score-response.schema.json`. | `scoring/thresholds/v1.yaml`, `scoring/gop.py` |
| 3 | Not fixed. A −9.1 drift artefact is still `wrong` under any threshold a native control can justify. | — |

Why en-us stays g2p_en rather than espeak-ng en-us: CLAUDE.md fixes the GOP pipeline as
g2p_en → ARPAbet→espeak map, and `lexicon.yaml`, numbers and contractions live there. espeak-ng
supplies the second accent only. Switching en-us to espeak-ng too is a one-line change in
`scoring/api.py` if wanted.

### Thresholds v1: how `wrong_below = −3.4` was derived

From the native control only, never from the Vietnamese recording (one recording; fitting to
it would fit noise). Full derivation in `services/speech/src/sonari_speech/scoring/thresholds/v1.yaml`:
good.wav ("one think you", one native US speaker, LibriSpeech), 9 phonemes, each word on its
better reference. Lowest GOP +1.47 (ŋ); margin = the spread of the same 9 values (6.33 − 1.47 =
4.86), stated before any held-out check; 1.47 − 4.86 = −3.39 → −3.4. The best rival must be about
30 times as likely as the expected phoneme before a phoneme is called wrong.

Checks (none moved the number):

- good.wav: 0 wrong, 0 unclear (test `test_the_native_control_gets_no_wrong_verdict`).
- "one tink you" on good.wav: /t/ −5.5, still wrong (P02's substitution).
- **Held out, the full source utterance** (27 phonemes): **1 wrong** on a native reading:
  "the" before a vowel, ə −3.62 heard ɪ. The speaker said ðɪ, which is correct; the reference
  holds only the citation form ðə. A reference problem, not a threshold problem; left visible
  (backlog).
- bad.wav "and took his dead": 2 wrong, both known: "and" strong form æ vs ə (−4.85), "dead"
  cut by the clip edge (ɛ −4.70).

So the requirement "a native speaker reading correctly gets no wrong verdicts" holds on the
control it was derived from, and fails once on 27 held-out native phonemes, for a known reason.

### Latency (12-core laptop, int8 model, 2.3 s of speech, 27 phonemes, 10 words, p50 of 50)

| Step | ms |
|---|---|
| decode + VAD + model (unchanged) | ≈ 690 (one run) |
| espeak-ng en-gb, one process per sentence | 12.5 |
| align + GOP, en-us only (before) | 4.2 |
| align + GOP, both accents (after) | 7.6 |

Added per request: ≈ 3.4 ms of CPU on the critical path; espeak-ng's 12.5 ms runs in a thread
while the model runs, so it is hidden whenever the model takes longer (always, here). The
model is not run twice: both alignments read the same posteriors.

## Known limit, not fixed this week: one frame per phoneme

Every phoneme in every response so far spans exactly one 20 ms frame (`endMs − startMs = 20`).
CTC posteriors are peaky: the model fires one frame per phoneme and emits blank elsewhere, and
the Viterbi path assigns the phoneme only to its spike. GOP is "mean over the phoneme's frames",
so it is a single frame's log-ratio, with no averaging: one noisy frame decides the verdict, and
a spike placed on a neighbour's frame (drift) produces the −9 outliers. Candidate fixes (score
over the spike plus its adjoining blank frames; posterior-weighted GOP; a CTC-aware GOP such as
GOP-SD) are for G1, measured on the evaluation set.

## Prediction for the evidence recording (hand reasoning, NOT a measurement)

Made from the GOP values quoted in the evidence above, not from a re-run: the response JSON is
not on this machine. Only 13 of the 17 wrong phonemes are described there; the other 4 cannot
be predicted.

Expected to stop being `wrong`:

| Phoneme | Evidence | Expected now | Why |
|---|---|---|---|
| "for" ɔːɹ | heard ɔː, −0.20 | correct (en-gb) or unclear | en-gb "for" is f ɔː; even on en-us, −0.20 is unclear |
| "parsley" ɑːɹ | heard ɑː | correct (en-gb) | en-gb is p ɑː s l i |
| "Poor" ʊɹ | heard value and GOP not quoted | probably unclear or correct | en-gb is p ʊə; depends on the realisation, uncertain |
| i/iː | −0.19 | unclear | inside the band |
| ə/ɐ ("away") | −1.06 | correct (en-gb) or unclear | espeak-ng en-gb itself writes ɐ |
| t | −0.65 | unclear | inside the band |

Expected to remain `wrong` (false alarms the changes do not touch):

| Phoneme | Evidence | Why it stays |
|---|---|---|
| "valued" l heard s | −9.1 | drift; far below −3.4; en-gb "valued" (v a l j uː d) aligns the same frames |
| "valued" j heard t | GOP not quoted | drift; presumably far below −3.4 like its neighbour |
| "thrown" n heard v | GOP not quoted | drift; en-gb only changes oʊ → əʊ |

Real errors, which should survive:

| Phoneme | Evidence | Risk |
|---|---|---|
| p heard b, twice | GOP not quoted | **if either GOP is between −3.4 and 0, it becomes unclear and the real error is lost.** This is the cost of the margin. |
| "looks" final s lost | not quoted | survives only if below −3.4 |
| θ heard d | not quoted | survives only if below −3.4 |

Expected word-level outcome: the words carrying only rhotic or near-pair misses ("for",
"parsley", probably "Poor", "away") move to `correct` or `unclear`; "valued" and "thrown" stay
`wrong` (drift); "its"/"looks"/"then" depend on the unquoted values. The first evaluation set
(recorded with `SPEECH_DEBUG_DUMP_DIR`) is what turns this into a measurement.

## Dev audio dump

`SPEECH_DEBUG_DUMP_DIR=/some/dir` keeps, per request, `audio<ext>` (bytes as received),
`request.json` (referenceText, filename, content type) and `response.json` (status and body,
including errors). Off unless set; refused (logged as an error) inside a container (`/.dockerenv`,
`/run/.containerenv`, or `$container`); the Dockerfile does not set it, and a test fails if it ever does.
