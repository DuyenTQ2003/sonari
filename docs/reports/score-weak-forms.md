# /v1/score: weak forms of function words, and thresholds v2

Date: 2026-10-08. Thresholds in service: `v2-native-ls400` (correct > 0, **wrong < −4.5**).
Reproduce: `make score-native` (about 5 min on a 12-core laptop; the main tables below are its
output). Builds on `score-native-calibration.md` (PR #51), whose audio and seed it reuses.

**Not measured here:** any Vietnamese speaker. v2 is calibrated on native read speech only; its
false-alarm rate on a learner is still the open question of PR #51's Part 2.

## What changed

1. **A closed list of ten function words gets other forms** (`g2p/weak_forms.yaml`, 16 forms):
   to, was, and, the, a, of, for, at, can, them. Each word is also scored against these, with the
   same per-word "best reference" rule that en-gb uses (`scoring/accents.py`: fewer wrong, then fewer
   unclear, then the higher mean GOP; a tie keeps the earlier one, en-us first). A word outside
   the ten has no other form; no rule generates one.
2. **Every form has a source** a test can check: a CMUdict variant (the ARPAbet must be in the
   vendored dictionary and map to the tokens), the entry's IPA in Wiktionary, espeak-ng 1.52's own
   reading of a short phrase (the model's training labels come from espeak-ng), or Wikipedia's
   "Weak and strong forms in English" (which cites the English Pronouncing Dictionary and Roach).
   The file says which. Forms I could not source were left out (listed in the file's header).
3. **Thresholds v2** is the default (`scoring/thresholds/v2.yaml`); v1 stays in the repo.
4. The `reference` field of a word stays `en-us` when a weak form wins (a weak form is not an
   accent); the phonemes' `expected` tokens show which form it was. Contract text updated first.

| word | reference (CMUdict's first variant) | forms added (sources) |
| --- | --- | --- |
| to | tuː | tə (CMUdict, Wiktionary, espeak-ng), tʊ (Wiktionary, espeak-ng) |
| was | wɑːz | wʌz (CMUdict, Wiktionary, espeak-ng), wəz (CMUdict, Wiktionary) |
| and | ənd | ænd (CMUdict, Wiktionary), ən (Wikipedia) |
| the | ðə | ði (CMUdict, Wiktionary), ðɪ (Wiktionary, espeak-ng) |
| a | ə | eɪ (CMUdict, Wiktionary), ɐ (espeak-ng) |
| of | ʌv | əv (CMUdict, Wiktionary) |
| for | fɔːɹ | fɚ (CMUdict, Wiktionary), fə (Wiktionary) |
| at | æt | ət (Wiktionary) |
| can | kæn | kən (CMUdict, Wiktionary) |
| them | ðɛm | ðəm (CMUdict, Wiktionary) |

Checked and left out: "to" tɪ (CMUdict alone), "was" wɔːz (a dialect vowel), "the" ðʌ (a stressed
variant), "and" n̩ (over the cap of two forms per word), "them" əm (that is 'em). The cap of two
exists because each form costs one more alignment pass.

## Native wrong rates, before and after

The same 400 LibriSpeech dev-clean utterances as PR #51 (seed 20261008, ≤ 15 s, 40 speakers,
24,010 phonemes). The us/gb rows of this run equal PR #51's on all 37,090 (max |ΔGOP| 0), so
"before" below is the same data re-read without the weak forms. Interval: 95% bootstrap over
utterances.

| references | wrong below | phonemes wrong | wrong per utterance | utterances with any |
| --- | --- | --- | --- | --- |
| en-us + en-gb (before) | −3.4 (v1) | 3.59% (3.37–3.84%) | 2.15 | 312 of 400 (78%) |
| en-us + en-gb (before) | −7.2 (PR #51's proposal) | 0.86% (0.75–0.97%) | 0.52 | 147 of 400 (37%) |
| + weak forms (after) | −3.4 (v1) | 1.61% (1.45–1.78%) | 0.97 | 211 of 400 (53%) |
| + weak forms (after) | **−4.5 (v2)** | **0.79% (0.67–0.92%)** | **0.47** | **125 of 400 (31%)** |

At v1's −3.4 the weak forms alone halve the native false alarms (3.59% → 1.61%). PR #51 predicted
−4.5 from a what-if that dropped to/was/and; the real run gives −4.5 as well.

## v2: chosen by PR #51's rule, nothing else

The highest threshold on a 0.1 grid, stepping down from −3.4, with native wrong under 1% **and** the
upper end of the 95% interval under 1%:

| wrong below | phonemes wrong (95% interval) | per utterance | verdict of the rule |
| --- | --- | --- | --- |
| −4.2 | 0.98% (0.85–1.12%) | 0.59 | point under 1%, upper end over |
| −4.3 | 0.94% (0.81–1.08%) | 0.56 | upper end over 1% |
| −4.4 | 0.90% (0.77–1.03%) | 0.54 | upper end over 1% |
| **−4.5** | **0.79% (0.67–0.92%)** | 0.47 | **chosen** |

Split half by speaker, at −4.5: 0.78% and 0.81%.

**The G0 gate holds.** `test_g0_clips` marks the substituted /t/ in "one tink you" wrong: −5.54,
1.04 nats below −4.5. (A v2 under −5.54 would have made it unclear and I would have stopped.)
good.wav: 9 of 9 correct. bad.wav "and took his dead": "and" is now correct (strong æ, which the
reference lacked: −4.85 before); the one miss left is "dead", cut by the clip edge.

### Held out

A second draw, seed 20261009, 400 utterances, **minus the 66 it shares with the first**: 334
utterances, 20,679 phonemes. Same 40 speakers (dev-clean has no others), so this is held out by
utterance, not by speaker; a speaker-disjoint check (test-clean) was not done. Seed chosen before
looking; `python -m score_eval.report native-20261009-400.jsonl --wrong-below -4.5 --without
native-20261008-400.jsonl` prints it.

| references | wrong below | phonemes wrong | wrong per utterance | utterances with any |
| --- | --- | --- | --- | --- |
| en-us + en-gb | −3.4 | 3.63% (3.39–3.91%) | 2.25 | 267 of 334 (80%) |
| + weak forms | −3.4 | 1.74% (1.53–1.95%) | 1.07 | 188 of 334 (56%) |
| + weak forms | **−4.5 (v2)** | **0.93% (0.78–1.11%)** | 0.58 | 116 of 334 (35%) |

The weak-form gain holds (3.63% → 1.74% at −3.4). **v2 is under 1% as a point estimate on both
samples, but on the held-out one its interval crosses 1%** (upper end 1.11%). That is what a
threshold picked at the edge of the rule does on new data; expect the true native rate to be
0.8–1.0%. If the owner wants margin: −5.0 gives 0.54% (0.45–0.64) and 0.60% (0.48–0.74) on the two
samples, and the G0 /t/ stays wrong (0.54 nats below). I shipped what the rule gives.

## What is left: the remaining native false alarms at −4.5

190 wrongs of 24,010 phonemes in 125 utterances (held-out: 193 of 20,679, in 116).

- **Function words no longer dominate**: 11% of the wrongs (13% held-out) fall in function words,
  which hold 26% of the phonemes; the ten listed words hold 2 of the 190 (3 of 193). Before the
  weak forms, 89% of the wrongs at −7.2 were function words.
- **They are reference problems of other kinds**, not a speaker's fault:
  - the merged vowel tokens **aɪə, aɪɚ, iə** (fire, quiet, diocese, society): 29 of the 190 (15%)
    from 57 phonemes; half of those phonemes are wrong, and the model hears aɪ (aɪə→aɪ 15, aɪɚ→aɪ 5);
  - the **flap**: reference t, speaker ɾ (water, city): t→ɾ 15 (19 of 1,730 t's; held-out 28, 32 of 1,447);
  - the **syllabic l**: reference ə, model əl: 10 (held-out 11); **ə→ɚ** 8;
  - **ə** is 41 of the 190 (22%) from 3.0% of its own occurrences (held-out 3.1%).
- **More short words in connected speech**, outside the ten: an 6, his 6, because 4, me 3, have 2
  (held-out: his 6, from 4, an 4, have 3). Probably reduced forms again; I have not listened to
  them. Candidates for the list, each needing a source; not added here, because choosing them from
  this sample and then setting the threshold on it would be fitting.
- **Spread:** the 10 commonest words hold 36 of the 190; no word has more than 6. By speaker the
  wrong share runs from 0.00% to 2.14% (median 0.67%); held-out 0.00% to 2.81% (median 0.83%).
- **Whole words failing together**: 4 observed against 0.51 expected by chance (diocese, them, me,
  his; held-out: have, from, her, hill; 10 of the 190 wrongs). PR #51 found none at −7.2 (1
  against 0.60). They are short words, not a collapse of the sentence around them.

### Expected native wrongs per practice sentence (6–14 words)

| basis | main sample | held-out |
| --- | --- | --- |
| wrong per word | 0.027 | 0.033 |
| per 6-word sentence, if wrongs fell evenly over words | 0.16 | 0.20 |
| per 14-word sentence | 0.38 | 0.46 |
| measured: native utterances of 6–14 words | 154 utterances: 0.27 wrong each, 21% with one | 122: 0.25, 22% |

So a native speaker reading a practice sentence correctly gets about **0.2–0.4 false "wrong"
phonemes**, and **about one sentence in five has at least one**. LibriSpeech is audiobook prose,
not the VOA practice sentences; a sentence with many t's between vowels, `-ire` words or `-le`
endings will be worse than that. The per-word rate (0.03) is the figure to scale, not the
sentence rate.

## Cost

Alignment + GOP (`score_accents`) with en-gb alone against en-gb plus the weak forms, median of 40:

| clip | words | en-us only | + en-gb | + en-gb + weak forms |
| --- | --- | --- | --- | --- |
| 1.4 s | 4 | 1.7 ms | 3.4 ms | 3.4 ms (no listed word) |
| 4.5 s | 16 | 6.3 ms | 13.7 ms | 28.5 ms |
| 13.3 s | 56 | 21.9 ms | 44.4 ms | 89.8 ms |

The weak forms add up to two passes: **+15 ms on a 4.5 s sentence, +45 ms on the longest clip the
service takes**, against a model pass of several hundred ms.

## Limits

- Read audiobook speech, mostly US; 40 speakers, shared by both samples.
- The list was motivated by PR #51's analysis of the same 400 utterances. The forms come from
  dictionaries, not from the data, and the threshold from the rule, but the sample is not
  independent of the idea: the held-out run is the check, and it is thinner (0.93%).
- Best-of also accepts more of what a learner says: a real error can match a variant. For
  these ten words every form is an English pronunciation, which is the intent; the learner
  evaluation (Part 2) should look for a miss this hides.
- Forms kept in the native run (`report.py`): a 97% ɐ for "a", 96–97% ænd for "and", 85% tə for
  "to"; ən, əv, ət, eɪ, ði are kept 0–5% of the time. They stay: each has a source, and a list
  pruned by this sample would be fitted to it.
- The espeak-ng source check runs only on espeak-ng 1.52 (the version the phrases were read
  with); CI and the Docker image install whatever apt gives, which skips it.
