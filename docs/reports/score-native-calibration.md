# /v1/score on native speech at scale: the "wrong" threshold

Date: 2026-10-08. Thresholds in service: `v1-native-g0` (correct > 0, wrong < −3.4, PR #50).
Reproduce: `make score-native` (about 4 min on a 12-core laptop; the tables below are its output).

**Part 2 (the Vietnamese evaluation set) is not done:** the recordings do not exist yet.

**Followed up** in `score-weak-forms.md`: the weak forms recommended below were added, and v2 (−4.5, not
−7.2) is the shipped threshold. This report is the measurement it started from; its numbers stand.

## Method

- **Sample:** 400 LibriSpeech dev-clean utterances (CC BY 4.0), seed 20261008, drawn from the
  utterances of at most 15 s (`Settings().max_clip_s`, what the service accepts). 40 speakers,
  24,010 phonemes. Every utterance is a native speaker reading its transcript; the transcripts
  are taken as correct.
- **Scoring:** `tools/score_eval/score.py` runs the service's own pieces: ffmpeg to WAV, the
  runtime (VAD trim, int8 model), g2p_en (en-us) and espeak-ng (en-gb), whole-sentence alignment,
  P02's GOP. It stores raw GOPs for both accents; `analyse.py` then applies a threshold and the
  service's per-word accent choice (which depends on the threshold, so it is redone per threshold).
- **Output:** `~/sonari-data/derived/score_eval/native-20261008-400.jsonl` (outside the repo).
- **v2 rule (stated before looking at candidates):** the highest threshold on a 0.1 grid whose
  native wrong share is under 1% **at the upper bound of a 95% bootstrap interval** (resampling
  whole utterances), not merely on this sample.

## Results

### GOP distribution (each word on its v1-chosen accent)

| quantile | 0.1% | 0.5% | 1.0% | 2.0% | 5.0% | 10.0% | 25.0% | 50.0% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GOP | -9.73 | -8.01 | -7.08 | -5.30 | -2.47 | -0.04 | +2.68 | +4.30 |

At or below 0 (not correct): 10.1% of native phonemes.

### 1. Native phonemes marked wrong

| wrong below | phonemes wrong (95% interval) | wrong per utterance | utterances with any |
| --- | --- | --- | --- |
| **−3.4 (v1)** | **3.59%** (3.37%-3.84%) | 2.15 | 312 of 400 (78%) |
| −7.0 | 0.95% (0.83%-1.07%) | 0.57 | 160 of 400 (40%) |
| **−7.2 (v2 proposal)** | **0.86%** (0.75%-0.97%) | 0.52 | 147 of 400 (37%) |

Split half by speaker (fit on 20 speakers, rate on the other 20): −7.1 → 0.83%, −6.9 → 1.07%.
−7.0 meets "under 1%" on this sample only; its interval crosses 1%, hence −7.2.

v1 does not hold up: a native reader reading correctly gets about 2 wrong phonemes per sentence,
and 78% of native sentences show at least one.

### 2. The proposed v2, and who the native false alarms are

**Proposal: wrong below −7.2.** Implied per-utterance rate: 0.52 wrong phonemes per native
utterance (mean 60 phonemes), and **37% of native utterances still get at least one "wrong".**
"Under 1% of phonemes" is not "a native speaker is rarely corrected".

**A few function words dominate**, and the cause is the reference, not the speaker:

| at | wrongs | in function words (26% of phonemes) | in **to / was / and** alone |
| --- | --- | --- | --- |
| −3.4 | 862 | 516 (60%) | 428 (50%) |
| −7.2 | 206 | 184 (89%) | 179 (87%) |

At −7.2: "to" 99 (uː heard ə), "was" 64 (ɑː heard ʌ), "and" 16 (ə heard æ). CMUdict's first
variant, which the en-us reference uses, is the strong form (tuː, wɑːz); read speech uses the
weak form (tə, wəz), which espeak-ng's en-gb citation form does not give either. "the" (33 at
−3.4, the ðɪ case of PR #50) drops out by −7.2. The rest at −7.2 is thin: because 4, live 2,
them 2, proper names (Prometheus, Brion, Celestine).

**What-if (not a scoring change):** without to/was/and, 1.91% are wrong at −3.4, and under 1%
needs only **−4.5** (0.92%), not −7.2.

**Why v2 is proposed here and not shipped.** −7.2 buys native silence by also silencing real
errors: P02's substitution in native audio ("one tink you", /t/ −5.54, the G0 gate case, and
`test_g0_clips` asserts it is wrong) would become "unclear". Most of the distance from −4.5 to
−7.2 exists only to absorb three words' strong forms. Recommendation for the owner to decide:
**fix the reference first** (accept the weak form of to/was/and and similar function words as
a further variant, the way en-gb is accepted now), re-run `make score-native`, and set v2 from
that run; it should land near −4.5. Shipping −7.2 now is the alternative if a single number is
needed this week; it meets the brief's rule, but every real substitution scoring between −7.2 and −3.4
(the G0 case among them) is then reported as "unclear", with no feedback.

### 3. Do native false alarms fail together as whole words?

| wrong below | words (≥ 2 phonemes) with most phonemes wrong | expected if wrongs were independent | wrongs in them |
| --- | --- | --- | --- |
| −3.4 | 8 | 10.68 | 21 of 862 |
| −7.2 | 1 | 0.60 | 2 of 206 |

**No.** On native read speech, wrong phonemes are isolated: whole-word failures occur no more
often than chance (8 seen against 10.7 expected at −3.4). Native false alarms are single
reference mismatches in short function words, not alignment collapse. So when a learner
recording shows a word where most phonemes fail together (as "valued" did), the native data
gives no sign that the scorer does this to correct speech; such a word is either a real
breakdown in the reading or alignment collapse triggered by the learner's deviations, and only
the evaluation set can tell which. That is Part 2, point 3.

## Limits

- Read audiobook speech by native (mostly US) speakers; not spontaneous speech, not British.
- The transcripts are assumed exact; LibriSpeech's are near-exact, so a few "wrongs" may be
  real misreadings. That can only lower the true false-alarm rate.
- One alignment frame per phoneme (PR #50's report) still holds: each GOP is one CTC spike.

## Part 2: when the recordings exist

Record with `SPEECH_DEBUG_DUMP_DIR` (PR #50) into a directory outside the repo; keep the notes
next to it. Never commit either: they are a person's voice. The scoring code in
`tools/score_eval/score.py` takes WAV bytes and a reference text, so the learner run is a loop
over the dump plus the notes; thresholds come from this report only.
