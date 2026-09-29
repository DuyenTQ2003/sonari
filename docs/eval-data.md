# Evaluation data

Where the audio for every pronunciation gate comes from. No recording is done for this
project: all evaluation audio is from public datasets with transcripts.

## Datasets

| Dataset | Licence | Speakers | Use here |
|---|---|---|---|
| LibriSpeech (`dev-clean`, `test-clean`) | CC BY 4.0 | Native English, read audiobooks | G0 pair, G1 main set |
| Common Voice (English) | CC0 | Mixed, includes non-native | G1 accent slice, G2 |
| L2-ARCTIC | Registration + own terms | Non-native, expert phoneme error labels | G2, if terms permit |

LibriSpeech is already 16 kHz mono FLAC, so no resampling is needed. Common Voice ships
MP3 at 32/48 kHz and must be converted.

Nothing from these datasets is committed. Audio lives under `DATA_DIR`
(default `~/sonari-data`), which `.gitignore` excludes.

```
$DATA_DIR/
  librispeech/dev-clean/...
  commonvoice/en/clips/...
  derived/
    g0/{good,bad}.wav
    g1/manifest.csv
    g2/manifest.csv
```

## The core problem, stated plainly

These datasets have **transcripts, not pronunciation error labels**. A transcript says
which words were spoken; it does not say whether /θ/ came out as /t/. Two consequences:

1. **Correct references are cheap.** A LibriSpeech clip of a native speaker reading
   "think" is a reliable positive: the phoneme was almost certainly produced correctly.
2. **Errors must be constructed.** There is no labelled set of Vietnamese-style
   substitutions. G1 builds them by **minimal-pair substitution**: take a clip whose
   transcript contains `think` and score it against the reference text `tink`. The
   audio is unchanged; the expected phoneme sequence is wrong on purpose.

That is a legitimate test of the scorer — it must give a low GOP for /t/ when the
speaker said /θ/, and name /θ/ as the competitor — but it is **not** the same as a
learner mispronouncing. Real errors are gradient and inconsistent; substituted
references are clean and absolute. The README says this.

## G0 — spike pair (P01, P02)

Two clips, chosen by script, not recorded:

- `good.wav`: a LibriSpeech utterance containing a word with initial /θ/ ("think",
  "three", "thought"), trimmed to that word plus a little context.
- `bad.wav`: a LibriSpeech utterance containing the nearest /t/-initial word ("tink"
  does not occur, so use "tin", "took", "talk") from **the same speaker** where
  possible, so voice is not a confound.

Gate G0 asks only: does the model's posterior for /θ/ differ clearly between the two?

## G1 — minimal-pair substitution set (P24, P25)

200 items, built by script from LibriSpeech.

For each of the eight Vietnamese-learner error types, find utterances containing a word
that carries the target phoneme, and construct a paired item:

| Condition | Audio | Reference text scored against |
|---|---|---|
| `match` | speaker says "think" | "think" — expect high GOP on /θ/ |
| `mismatch` | speaker says "think" | "tink" — expect low GOP on /t/, competitor /θ/ |

Error types, same list the product targets:

| Code | Contrast | Example word pairs |
|---|---|---|
| `TH_T` | /θ/ vs /t/ | think–tink, three–tree, both–boat |
| `DH_D` | /ð/ vs /d/ | they–day, other–udder |
| `SH_S` | /ʃ/ vs /s/ | she–see, ship–sip |
| `AE_E` | /æ/ vs /e/ | bad–bed, man–men |
| `IY_I` | /iː/ vs /ɪ/ | sheep–ship, leave–live |
| `FIN_DEL` | final consonant present vs absent | book–boo, hard–har |
| `CLU_RED` | cluster vs reduced | desks–dess, asked–ast |
| `Z_S` | final /z/ vs /s/ | rise–rice, buzz–bus |

Aim for ~12 items per type, each with both conditions. Selection is deterministic
(fixed seed) and the manifest records speaker id, source file, offsets and the
constructed reference.

**Split by source utterance**, never by file: an utterance's match and mismatch items
must not land on opposite sides of the train/test split.

## G2 — accented speech

Common Voice has accent metadata on some clips. Build a slice of non-native speakers
(no Vietnamese subset exists; that is the point of the gap statement) and repeat the
G1 construction. If L2-ARCTIC access is obtained and its terms allow, use its expert
phoneme annotations instead — those are real labelled errors, not constructed ones.

G2 is reported, not blocking. A large G1–G2 gap means the scorer is tuned to clean
native speech.

## G3 — real learners (backlog)

Pearson r against human ratings of real Vietnamese learners. Needs consented user audio
from launch. Open until then, and stated as open.

## Honesty rules (these go in the README)

- The evaluation set is **native English speakers**. The product's users are
  Vietnamese. That gap is not closed by any number in this repo.
- G1 errors are constructed by substituting the reference text, not produced by a
  learner. Real mispronunciations are messier and harder to detect.
- Thresholds are fitted on train and reported on held-out test. The split seed is
  recorded. Never tune against test.
- While G3 is open, the app labels pronunciation scoring as beta and presents "sounds
  to work on" rather than an absolute measurement of the learner.
