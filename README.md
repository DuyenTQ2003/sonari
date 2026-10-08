# Sonari

Sonari is an English speaking-practice app for Vietnamese learners working toward IELTS (the MVP
targets band 4.5–5.0). The learner reads a sentence aloud. The app aligns the recording to the
sentence's expected phonemes, gives each phoneme a verdict (correct, unclear or wrong), and explains
each wrong one in Vietnamese: what was heard and how to place the tongue and lips. This repository
is a working demo of that loop: one practice page and 20 sentences from VOA Learning English. It
does not give an overall score, because the thresholds behind the verdicts are calibrated on native
speech only (below).

![The practice page](docs/img/practice.png)

```bash
make demo        # fetch the model and CMUdict, start MongoDB and Redis, load the 20 sentences, start the apps
```

Then open http://localhost:3000. Prerequisites and each step on its own: [Run it](#run-it).

## What is technically distinctive

**Phonemes, not words.** The speech service runs `wav2vec2-lv-60-espeak-cv-ft`, a model that
outputs espeak phonemes rather than words, quantised to int8 ONNX and run on CPU. The sentence's
expected phonemes come from `g2p_en` (CMUdict, then a neural guess) through an ARPAbet-to-espeak
table. The whole sentence is force-aligned to the model's frame posteriors with a CTC Viterbi pass.
Each phoneme then gets a goodness-of-pronunciation score:

```
GOP = mean over the phoneme's frames of ( log p(expected) − max over other phonemes log p(q) )
```

The method passed its first gate on native audio. On the same frames, /θ/ in "think" scored +3.886
and the same audio scored against a substituted /t/ scored −5.713, with θ named as what was heard
([spikes/gop/RESULTS.md](spikes/gop/RESULTS.md)).

**Three references per word, best one kept.** A correct reading can differ from one dictionary
form, so each sentence is aligned against:

- en-us (g2p_en),
- en-gb (espeak-ng),
- the weak forms of a closed list of ten function words (to, was, and, the, a, of, for, at, can,
  them).

Each word keeps the reference it fits best ([scoring/accents.py](services/speech/src/sonari_speech/scoring/accents.py)).
Every weak form has a source that a test checks: a CMUdict variant, Wiktionary, espeak-ng, or
Wikipedia's weak-forms table, which cites the English Pronouncing Dictionary
([g2p/weak_forms.yaml](services/speech/src/sonari_speech/g2p/weak_forms.yaml)). On 400 native
utterances at the old threshold (−3.4), the weak forms cut native phonemes marked wrong from 3.59%
to 1.61% ([score-weak-forms.md](docs/reports/score-weak-forms.md)).

**Three verdicts, and only one is an error.** Correct is above GOP 0, wrong below the threshold,
and unclear between. Only "wrong" carries feedback, and the feedback is a message key, not text.
The Vietnamese explanation comes from a lookup table, and each rule names its source
([scoring/feedback.yaml](services/speech/src/sonari_speech/scoring/feedback.yaml),
[messages/vi.json](apps/web/messages/vi.json)). There is no LLM at runtime.

**Why not Whisper.** Speech recognition (STT) is never used for scoring
([CLAUDE.md](CLAUDE.md), [PLAN §7.4](docs/PLAN-v7.md)). A recogniser with a language model
outputs the word it expects, so a mispronounced word can come back spelled correctly and the
error disappears. This is a design rule; the repo holds no measurement of it.

## How the "wrong" threshold was set

The rule was fixed before the candidates were looked at. Take the highest threshold, stepping down
by 0.1 from −3.4, at which fewer than 1% of native phonemes are marked wrong, **and** the upper end
of the 95% bootstrap interval (resampling whole utterances) is under 1% too. Every word is scored
with all three references.

Selection sample: LibriSpeech dev-clean, seed 20261008, 400 utterances, 40 speakers. Validation
sample: seed 20261009 minus the 66 utterances shared with the first, 334 utterances, same speakers.

| Wrong below | Selection: native wrong (95% interval) | Validation: native wrong (95% interval) | |
| --- | --- | --- | --- |
| −3.4 (v1) | 1.61% (1.45–1.78%) | 1.74% (1.53–1.95%) | fails |
| −4.5 | 0.79% (0.67–0.92%) | 0.93% (0.78–1.11%) | passes selection, **fails validation** |
| **−5.0 (shipped)** | **0.54% (0.45–0.64%)** | **0.60% (0.48–0.74%)** | passes both |

Sources: [score-weak-forms.md](docs/reports/score-weak-forms.md) and
[thresholds/v2.yaml](services/speech/src/sonari_speech/scoring/thresholds/v2.yaml), version
`v2-native-s20261008-val20261009`. To reproduce: `make score-native`.

Costs, as measured:

- At −5.0, native speech still gets 0.33 wrong phonemes per utterance on the selection sample.
- Real errors with a GOP between −5.0 and −4.5 are reported as unclear, with no feedback.
- The gate case from the GOP gate above stays wrong, but only just. In the current pipeline, /t/
  in "one tink you" scores −5.54, 0.54 below the line
  ([test_g0_clips.py](services/speech/tests/scoring/test_g0_clips.py)).

The native false alarms left are mostly reference problems, not speaker errors: the merged vowel
tokens aɪə/aɪɚ/iə, the flap, and the syllabic l. Those counts were taken at −4.5
([score-weak-forms.md](docs/reports/score-weak-forms.md)).

### On Vietnamese speakers

**No measurement yet.** The evaluation set of Vietnamese recordings ("Part 2" in
[score-native-calibration.md](docs/reports/score-native-calibration.md)) has no report in
`docs/reports`.

The only Vietnamese measurement in the repo is one recording of one sentence, scored with the
first threshold (GOP > 0): 17 of 32 phonemes and all 9 words were marked wrong
([score-false-alarms.md](docs/reports/score-false-alarms.md)). The en-gb reference, the unclear
verdict, the weak forms and v2 all came after it, and none has been measured on that recording.

## Limitations

- **Calibrated on native speech only.** The calibration audio is LibriSpeech audiobook readings
  by mostly US speakers. How often a Vietnamese learner who reads correctly is marked wrong is
  not measured.
- **The Vietnamese evaluation set** will be one speaker, the author. Its size and results go here
  when its report exists. One speaker cannot show how the scorer behaves across learners.
- **The validation sample shares its 40 speakers** with the selection sample; LibriSpeech
  dev-clean has no others. A speaker-disjoint check (test-clean) is not done.
- **Single-frame GOP.** CTC posteriors are peaky: every phoneme in every response so far spans one
  20 ms frame, so one frame decides each verdict ([score-false-alarms.md](docs/reports/score-false-alarms.md)).
- **Browsers.** The recorder was checked in headless Chromium and Firefox with fake microphones.
  It is untested on Safari, iOS, any phone, a real microphone and a screen reader
  ([apps/web/README.md](apps/web/README.md), [HANDOFF](docs/HANDOFF.md)).
- **Content.** One unit (*Study and work*), 20 sentences. Pronunciation only: no fluency or
  task-completion score, no listening, no accounts in the UI.
- **The Vietnamese copy** (feedback and UI) still needs a native reader before launch.

## Data pipeline

Ownership rules ([ADR-0006](docs/adr/0006-source-first-authoring.md)):

- No English text is generated, at any level.
- Source text is VOA Learning English, using only items credited to VOA staff.
- The pipeline is deterministic and keeps its provenance: no LLM, and every count below comes from
  a script with a report.

| Step | Count | Report |
| --- | --- | --- |
| Article URLs in VOA Learning English's sitemaps | 67,337 | [voa-corpus.md](docs/reports/voa-corpus.md) |
| Pages crawled (a random 71%, polite, resumable) | 47,854 | [voa-corpus.md](docs/reports/voa-corpus.md) |
| Passages of 100 words or more | 19,918 | [voa-corpus.md](docs/reports/voa-corpus.md) |
| Usable at level 4 as published | 48 | [voa-corpus.md](docs/reports/voa-corpus.md) |
| Usable after removing at most 5% of words, whole lines only ([ADR-0008](docs/adr/0008-boilerplate-trimming-removes-whole-lines-only.md)) | 724 | [voa-trim-corpus.md](docs/reports/voa-trim-corpus.md) |
| Lines removed by the trim / judged wrongly removed on reading | 1,273 / 0 | [voa-trim-corpus.md](docs/reports/voa-trim-corpus.md) |
| Single-topic explainers or news items among the 724 | 370 | [voa-classify.md](docs/reports/voa-classify.md) |
| Of those, with no topic-safety flag (default rule) | 257 | [voa-safety-stems.md](docs/reports/voa-safety-stems.md) |
| Practice sentences in this demo / passages they come from | 20 / 13 | [items.jsonl](tools/speaking_items/items.jsonl) |

**Provenance.** Each stored passage keeps the text as VOA published it, the trimmed text, and every
removed line with the rule that removed it. A re-trim adds a new version and never overwrites one
([ADR-0010](docs/adr/0010-source-versions-are-immutable-one-is-current.md)). Each practice sentence
pins the passage version it comes from, and the ingest refuses a sentence that is not in that
passage unchanged.

The 13 passages are committed as [tools/speaking_items/sources.jsonl](tools/speaking_items/sources.jsonl),
so the demo needs no crawl. The full crawl takes about 14 hours
([fresh-clone.md](docs/reports/fresh-clone.md)).

## Architecture

```
browser ── Next.js 15 (apps/web, :3000) ──┬── core   FastAPI (:8000)  identity, content; MongoDB rs0, Redis
                                           └── speech FastAPI (:8001)  G2P, int8 wav2vec2 (ONNX), alignment, GOP
```

Processes are split by resource profile, not by domain. Speech holds the model weights and sheds
load with 503 instead of taking core down. The contexts inside core never import or query each
other; an import check fails the build if they do. The response contract is a JSON Schema in
[packages/contracts](packages/contracts/schema/score-response.schema.json), and tests validate both
the service and the web fixtures against it.

| ADR | Decision |
| --- | --- |
| [0001](docs/adr/0001-modular-monolith-split-by-resource-profile.md) | Modular monolith: seven bounded contexts, each with its own database; processes split by resource profile (core, speech; later ai-gateway, worker) |
| [0004](docs/adr/0004-llm-api-not-self-hosted-gpu.md) | Production uses hosted LLM APIs, not a self-hosted GPU (recorded estimate: $2–8 a month against about $197) |
| [0006](docs/adr/0006-source-first-authoring.md) | Source-first authoring: real VOA (or Tatoeba) text at every level; an LLM writes only scaffolding |
| [0007](docs/adr/0007-transactional-outbox-for-events.md) | Events leave a context through a transactional outbox in MongoDB, then go to Redis Streams |
| [0008](docs/adr/0008-boilerplate-trimming-removes-whole-lines-only.md) | Boilerplate trimming removes whole lines only, at most 5% of a passage, each removal recorded |
| [0010](docs/adr/0010-source-versions-are-immutable-one-is-current.md) | A Source version is immutable; one version of each passage is current |

## Designed, not built

What the ADRs and [PLAN-v7](docs/PLAN-v7.md) describe and this demo does not have:

- **Two of the four processes.** `ai-gateway` (LLM calls, prompts, failover) and `worker` (content
  pipeline, TTS batches) do not exist.
- **Four of the seven contexts.** `learning`, `gamification` and `analytics` are declared with no
  code, and `tutor` does not exist. `identity` (with auth) and `content` are built.
- **LLM use.** There is no LLM call anywhere in the repo yet (ADR-0004 is unexercised), and no
  generated scaffolding: no questions, distractors, glosses or grammar explanations.
- **Units built from passages** (ADR-0006): the 12 words and one grammar point per unit, the
  exercises and the learnables. The demo has only the 20 practice sentences.
- **Scoring beyond pronunciation:** fluency, task completion, free speech (STT for transcripts),
  per-phoneme thresholds, and an overall score.
- **Levels and learning:** seven levels (the MVP is level 4), listening, spaced repetition,
  streaks and XP, and passage audio (the TTS spike only is in [spikes/tts](spikes/tts)).
- **Deployment:** a speech Dockerfile exists but has not been built here, and nothing is deployed.

## Run it

**Prerequisites**, with the versions this was run with:

| Tool | Version used | Why |
| --- | --- | --- |
| git, GNU make | 2.53, 4.4.1 | |
| [uv](https://docs.astral.sh/uv/) | 0.12.22 | Python 3.11 and both services' packages (uv downloads Python itself) |
| Node.js | 22.22.1 | the web app (`engines: node >= 22`); in WSL, install it inside the distro |
| Docker with Compose v2 | not run in the fresh-clone check (below) | MongoDB 7.0 (replica set `rs0`) and Redis 7 |
| ffmpeg | 8.0.1 | decodes the browser's recording |
| espeak-ng | 1.52.0 | the en-gb reference |

On Debian or Ubuntu, `sudo apt install ffmpeg espeak-ng`.

**Steps, in order.** `make demo` runs steps 2–7:

```bash
git clone https://github.com/duyentq-aie/sonari.git && cd sonari
make setup                    # 1. git hooks (pre-commit, commit-msg)
make apps/web/node_modules    # 2. npm ci for the web app
make speech-data              # 3. model from Hugging Face, kept only if its size and SHA-256 match
                              #    services/speech/src/sonari_speech/runtime/models.yaml; then CMUdict
make infra                    # 4. .env from .env.example, then MongoDB and Redis; waits until healthy
make ingest-demo-sources      # 5. the 13 VOA passages the sentences come from
make ingest-speaking-items    # 6. the 20 practice sentences
make dev                      # 7. core :8000, speech :8001, web :3000
```

Model and CMUdict go to `DATA_DIR` (default `~/sonari-data`), outside the repo. To check the model
without downloading: `uv run --directory services/speech python -m sonari_speech.runtime.weights --check`.

**Measured from a fresh clone** ([fresh-clone.md](docs/reports/fresh-clone.md)), with empty caches:

- Steps 1–3 and the scoring path took **108 s from `git clone` to a scored sentence**. The speech
  service was started by hand on another port, and 27 s of the 108 s was a web build that scoring
  does not need.
- Network was needed for the clone, Python, the packages, the model (355 MB), CMUdict and npm.
- **Steps 4–7 were not run in that check**, for two reasons:
  - Docker does not start in the WSL distro used.
  - The Makefile and `compose.yaml` fix the host ports (27017, 6379, 8000, 8001, 3000), so a
    second stack cannot run beside an existing one.

  CI covers the seed instead ([test_demo_seed.py](services/core/tests/test_demo_seed.py)).

## Development

`make lint typecheck test` is what CI runs (three jobs: repo, core, speech); the real-model tests
skip without the weights. Squash merges after three green checks. Notes: [docs/HANDOFF.md](docs/HANDOFF.md),
open ideas: [docs/backlog.md](docs/backlog.md).

Sonari is not affiliated with IELTS, British Council, IDP or Cambridge. Practice text comes from
[VOA Learning English](https://learningenglish.voanews.com/) (VOA-staff items, public domain).
Calibration audio is LibriSpeech (CC BY 4.0) and is not stored in the repo.
