# Build prompts

Session prompts for Claude Code, from empty repo to production. One prompt = one
session = one commit (or a small series). Run them in order within a track.

## How to use

1. Start a fresh Claude Code session in the repo root. `CLAUDE.md` loads automatically.
2. Paste the **session preamble** once, then one prompt.
3. If a prompt says **Revise before running**, first give Claude the listed inputs
   (spike numbers, schema, inventory) and ask it to adapt the prompt. Then run it.
4. Never merge two prompts into one session to "save time". The token budget runs out
   mid-task and leaves an uncommittable state.

## Tracks and order

```
Track AI:  P01 → P02 → P03 → P04 ─────────────→ P20 → P21 → P22 → P23 → P24 → P25
Track BE:        P10 → P11 → P12* → P13 → P14 → P15 → P17
Track FE:                     P12* → P16 ──────→ P30 → P31 → P32
Content:   P05, P06 (any time in M0)
* P12 needs the A6 design (design-system.md §7.1) done in a design tool first.
Then: M3 P33–P35 → M4 P40–P48 → M5 P50–P56 → M6 P60–P64 → M7 P70–P74
```

Hard gates:
- **P02** decides whether GOP works at all. If the gate fails, stop all tracks and
  re-plan.
- **P25** is gate G1 (minimal-pair error detection). If it fails, switch to word-level
  scoring and continue. See PLAN-v7 §9.1 for why G1/G2 replaced a Pearson r gate.

## Session preamble (paste first in every session)

```text
Read CLAUDE.md and docs/HANDOFF.md. Do only the task below. Before writing code,
list the files you will create or change and the command that proves the task is
done. Stop and ask if a requirement conflicts with an ADR or with CLAUDE.md. At the
end: run the checks, update docs/HANDOFF.md (done / next / blockers, under 40 lines),
and propose a conventional commit message. Talk to me in Vietnamese; everything you
write in the repo is English.
```

---

# M0 — Spike

### P01 — Eval data bootstrap + wav2vec2 phoneme spike
Depends on: — · Revise before running: no

```text
Task: fetch public evaluation audio, build the G0 pair by script, and prove that
wav2vec2 phoneme recognition separates the two sounds. Read docs/eval-data.md first.
No audio is recorded by hand anywhere in this project.

Setup
- spikes/gop/ with its own pyproject (uv). Dependencies: torch (CPU), transformers,
  soundfile, numpy, pandas. This spike may use torch; production will not.
- Model: facebook/wav2vec2-lv-60-espeak-cv-ft.
- All data under DATA_DIR (default ~/sonari-data), never in the repo.

Do
1. tools/evaldata/fetch_librispeech.py: download and extract dev-clean into DATA_DIR,
   with a checksum check and a resume-safe download. Print the licence (CC BY 4.0) and
   write DATA_DIR/librispeech/LICENCE-NOTE.md.
2. tools/evaldata/index.py: parse the transcripts into a dataframe of
   (utterance_id, speaker_id, flac_path, text, duration); cache it as parquet.
3. tools/evaldata/build_g0.py: pick one utterance containing a word with initial
   /theta/ (think, three, thought, thank) and one containing a /t/-initial word (tin,
   took, talk, time), preferring the same speaker. Cut each to the target word plus
   ~0.3 s of context, convert to 16 kHz mono WAV, and write
   DATA_DIR/derived/g0/{good,bad}.wav plus g0_manifest.json recording the source
   utterance ids, speaker ids and words chosen.
4. spikes/gop/run_spike.py: run the model on both files, greedy CTC decode, print the
   phoneme sequence for each, and print frame-level posteriors for the theta and t
   tokens (max over frames, mean of the top-5 frames).
5. spikes/gop/RESULTS.md: the decodes, the numbers, and the manifest contents.

Done when
- `uv run python tools/evaldata/build_g0.py` produces both wavs with a manifest.
- RESULTS.md states plainly whether each clip decodes the expected phoneme. Do not
  interpret a failure as success. If both decode the same, say so and stop.
```

### P02 — forced alignment + naive GOP (HARD GATE)
Depends on: P01 passed · Revise before running: no

```text
Task: align the expected phoneme sequence to audio and compute a naive GOP per
phoneme.

Do
1. spikes/gop/align.py: implement CTC Viterbi forced alignment in numpy over the
   log-posteriors (blank handling, repeated tokens). Do not depend on torchaudio's
   forced_align: the production image will run onnxruntime + numpy only. Keep it
   under 120 lines with a unit test on a synthetic posterior matrix.
2. The expected sequence comes from the g0 manifest's target word, written as espeak
   IPA tokens that exist in the model vocab (read vocab.json to confirm spelling).
   Also score the good clip a second time against a substituted reference (theta
   replaced by t) — that mismatch case is what G1 generalises.
3. For each aligned phoneme segment compute:
     gop = mean over frames of (log p(expected) - max_{q != expected} log p(q))
   and record the argmax competitor q.
4. Export each segment as a small wav (segments/<file>_<idx>_<phone>.wav) so the
   placement can be checked.
5. Append results to RESULTS.md: segment boundaries in ms, gop, competitor, for both
   files.

Gate (write the verdict in RESULTS.md)
- PASS if the gop for the correct reference is clearly higher than for the
  substituted reference on the same audio, and the competitor named in the
  substituted case is the phoneme the speaker actually produced.
- FAIL otherwise. On FAIL, do not tune thresholds to force a pass. List three
  hypotheses (clip selection, token mapping, model) and stop.
```

### P03 — ARPAbet → espeak IPA mapping
Depends on: P02 PASS · Revise before running: no

```text
Task: map g2p_en output (ARPAbet with stress digits) to the model's espeak IPA
tokens, and prove the mapping on 200 words.

Do
1. spikes/gop/phoneset/arpabet_to_espeak.yaml: one entry per ARPAbet phone (stress
   stripped). Where one ARPAbet phone maps to two tokens (diphthongs, affricates),
   map to the token sequence the model vocab actually contains. Choose US English;
   note every choice that depends on the accent in comments.
2. phoneset/check_vocab.py: assert every mapped token exists in the model vocab.json.
3. phoneset/roundtrip_test.py: take 200 common words (NGSL head, committed as a txt
   file), convert with g2p_en + map, and compare against espeak-ng output (via the
   phonemizer package, en-us) after the same normalisation.
4. Report agreement rate and the full list of mismatches in phoneset/REPORT.md.

Done when
- check_vocab passes (100% of mapped tokens exist).
- REPORT.md lists the agreement rate and every mismatch, each classified as
  mapping bug, accent variant, or g2p error. Fix all mapping bugs before finishing.
```

### P04 — ONNX export + CPU benchmark
Depends on: P02 PASS · Revise before running: no

```text
Task: export the model to ONNX, verify numerical parity, and measure CPU latency on
hardware matching the target VPS.

Do
1. spikes/gop/onnx/export.py: export with a dynamic time axis. Opset as supported by
   the installed torch.
2. onnx/parity.py: run torch and onnxruntime on good.wav and bad.wav. Report max abs
   difference of log-posteriors and whether the greedy decode is identical.
3. onnx/quantize.py: dynamic int8 quantisation. Repeat parity and also rerun the
   P02 GOP numbers with the quantised model.
4. onnx/bench.py: latency for 3 s and 8 s clips, 50 runs after 5 warmups, p50/p95,
   with intra_op threads = 1, 2, 4. Print model size on disk and peak RSS.
5. Write onnx/BENCH.md with a table and the CPU model name (lscpu).

Done when
- BENCH.md exists with fp32 vs int8 rows.
- It states whether int8 changes the P02 verdict. If it does, int8 is rejected.
- It gives the max concurrent scoring requests the VPS can serve under 2 s p95.
```

### P05 — Kokoro TTS spike
Depends on: — · Revise before running: no

```text
Task: check that Kokoro-82M is good enough for course audio.

Do
1. spikes/tts/: generate one VOA-style sentence at 0.8x, 1.0x and 1.15x, and a
   6-turn two-voice dialogue (two different voices). Use a sentence from a real VOA
   item, not invented text; put its URL in the README.
2. Measure real-time factor on CPU.
3. spikes/tts/CHECKLIST.md: a listening checklist for me to fill in (intelligibility,
   final consonants audible, unnatural stress, speed artifacts at 0.8x).

Done when
- The wav files and CHECKLIST.md exist and the RTF is recorded.
- Do not judge quality yourself; I fill in the checklist.
```

### P06 — VOA inventory (metadata only)
Depends on: — · Revise before running: no

```text
Task: count usable VOA Learning English items per level and topic, so the
curriculum can be sized. Collect metadata only, no bulk content.

Do
1. tools/voa_inventory/: a polite crawler (robots.txt respected, 1 req/s, cached
   responses, custom User-Agent with contact email from env).
2. For each item record: url, title, program (e.g. Let's Learn English, level 2/3
   news), date, byline, has_audio, audio_url, word_count, and a license_ok flag that
   is true only when the byline is VOA staff and the item is not marked as wire
   content (AP, Reuters, AFP).
3. Topic tagging: match titles and first paragraph against the level 4 candidate
   topics in PLAN-v7 §4.1 with a keyword list per topic. Keep the lists in YAML.
4. Output data/voa_inventory.csv and docs/voa-inventory.md with counts per
   level × topic, license_ok only.

Done when
- The CSV and summary exist.
- The summary names every level 4 topic with fewer than 2 usable items with audio.
  Those topics must be swapped (ADR-0006); list replacement candidates.
```

---

# M1 — Foundation

### P10 — Monorepo skeleton + Makefile + CI
Depends on: — · Revise before running: no

```text
Task: create the monorepo skeleton from CLAUDE.md "Repo layout".

Do
1. services/core and services/speech: uv projects, Python 3.11, src layout, ruff,
   mypy (strict for src), pytest. Each has a trivial /healthz and one test.
2. apps/web: leave empty with a README; P16 builds it.
3. packages/contracts: empty schema/ dir and README.
4. Root Makefile targets: dev, lint, typecheck, test, test-core, test-speech, fmt.
   `make test-speech` must not load model weights yet.
5. pre-commit: ruff, ruff-format, end-of-file, trailing whitespace, a check that
   rejects Vietnamese characters in .py files outside tests/fixtures (the language
   rule; UI copy lives in vi.json).
6. GitHub Actions: lint + typecheck + test per service, with caching.

Done when
- `make lint typecheck test` passes locally and in CI.
- The Vietnamese-character check has a test proving it catches "Xin chào" in a .py
  file.
```

### P11 — Compose: MongoDB replica set + Redis
Depends on: P10 · Revise before running: no

```text
Task: local infrastructure with a working MongoDB transaction.

Do
1. compose.yaml: mongo (--replSet rs0, healthcheck that initiates the set if needed),
   redis 7 with AOF, both with named volumes.
2. infra/mongo/mongo-init.js: create one database per bounded context and a user per
   service with access only to its own databases. Take the seven context names from
   docs/adr/0001. If ADR-0001 is not in the repo or does not list them, STOP and ask
   me. Do not invent context names.
3. .env.example with connection strings using directConnection=true for dev.
4. services/core/tests/integration/test_transaction.py: a multi-document transaction
   in one context database that commits, and one that aborts and leaves no data.
   Skip with a clear message if Mongo is not reachable.
5. `make dev` starts the infra; `make infra-reset` wipes volumes.

Done when
- `make dev && make test-core` runs the transaction test green.
```

### P12 — Contracts: ScoreResponse + events + codegen
Depends on: A6 designed in a design tool · Revise before running: YES — paste the A6 design

```text
Task: freeze the API contract that A6 needs, before speech-service exists.

Inputs I will paste: the final A6 design (screenshot or description).

Do
1. packages/contracts/schema/score-response.schema.json (JSON Schema 2020-12),
   derived from what A6 renders and nothing more. Expected shape (adjust to the
   design, and justify every field against a pixel on A6):
     scoringVersion, thresholdsVersion, overall (0-100), level ("word"|"phoneme"),
     words[]: {text, startMs, endMs, score, verdict: good|ok|bad,
               phonemes[]: {expected, actual|null, startMs, endMs, score, verdict}}
     fixes[] (max 3): {phoneme, substitutedBy|null, messageKey, exampleWord,
                       referenceAudioKey}
   messageKey is an i18n key, never Vietnamese text.
2. schema/events/*.schema.json: UserRegistered, AttemptScored, ExerciseAnswered,
   LessonCompleted. Each has eventId (uuid), occurredAt, version.
3. Codegen: Pydantic v2 models (datamodel-code-generator) into
   packages/contracts/python, TS types (json-schema-to-typescript) into
   packages/contracts/ts. `make contracts` regenerates both.
4. CI fails if generated code is out of date.
5. fixtures/: score-good.json and score-bad.json that validate against the schema.

Done when
- `make contracts` is idempotent and fixtures validate in both a Python and a TS test.
```

### P13 — core service skeleton + OTel
Depends on: P11, P12 · Revise before running: no

```text
Task: production-shaped skeleton for services/core.

Do
1. App factory, pydantic-settings config, structured JSON logging with trace ids.
2. Per-context Beanie initialisation: each context module owns its database handle.
   Add an import-linter (or a pytest check) forbidding imports between context
   packages except through contracts and events.
3. OpenTelemetry: FastAPI, Motor/PyMongo and Redis instrumentation, OTLP exporter
   configurable, disabled in tests.
4. /healthz (liveness) and /readyz (Mongo + Redis ping).
5. Error envelope: {error: {code, messageKey, details}}. messageKey maps to vi.json.

Done when
- Tests cover readyz failing when Mongo is down (use a fake).
- The cross-context import check fails on a deliberately bad import in a test fixture.
```

### P14 — Auth: JWT + refresh rotation
Depends on: P13 · Revise before running: no

```text
Task: identity context with email/password auth.

Do
1. Register, login, refresh, logout. Passwords with argon2id.
2. Access token 15 min (JWT, in memory on the client), refresh token 30 days in an
   httpOnly Secure SameSite=Lax cookie. Store refresh tokens hashed, with a family id.
3. Rotation with reuse detection: presenting an already-rotated refresh token
   revokes the whole family.
4. Cloudflare Turnstile verification on register (secret from env; a test double in
   tests).
5. Redis rate limit on login and register (sliding window), returning 429 with a
   messageKey.
6. Emit UserRegistered.

Done when
- Tests: happy path, wrong password, expired access, rotation, reuse-detection revoke,
  rate limit.
```

### P15 — Event bus: outbox + Redis Streams
Depends on: P13 · Revise before running: no

```text
Task: reliable events between contexts without cross-context joins.

Do
1. Outbox: a context writes its state change and an outbox document in the same
   Mongo transaction. A relay publishes outbox entries to Redis Streams and marks
   them sent. Record in a new ADR (next free number in docs/adr/) why not publish directly after
   commit (lost events on crash).
2. Consumer base class: consumer groups, ack after handler success, retry with a
   max-deliveries dead-letter stream, idempotency via a processed-event-id set per
   consumer (TTL).
3. Refactor P14's UserRegistered to go through the outbox.

Done when
- Tests: event delivered exactly-once-in-effect after a simulated relay crash
  between publish and mark-sent; poison message ends in the dead-letter stream.
```

### P16 — Web skeleton
Depends on: P12 · Revise before running: no

```text
Task: apps/web foundation with the design system wired in.

Do
1. Next.js 15 App Router, TypeScript strict, pnpm.
2. Tailwind theme from docs/design-system.md §1–3 tokens (colours, radii, spacing,
   shadows, motion). No other palette.
3. Fonts: Be Vietnam Pro (vietnamese subset) and Charis SIL for an <Ipa> component.
   A test renders /θ ð ʃ ʒ ŋ æ ɪ ʊ ɜː/ and asserts the Charis font family is applied.
4. next-intl with messages/vi.json. ESLint rule (or a script in CI) that fails on
   Vietnamese diacritics inside .tsx outside messages/.
5. shadcn/ui init, TanStack Query provider, a typed API client using
   packages/contracts/ts, Zustand only for recorder UI state.
6. Playwright smoke test at 390px width.

Done when
- `pnpm build`, lint, unit tests and the Playwright smoke test pass in CI.
```

### P17 — Mock speech-service
Depends on: P12 · Revise before running: no

```text
Task: a speech-service stub so FE and BE can build the launch flow before GOP is real.

Do
1. services/speech: POST /v1/score (multipart audio + referenceText) returning
   fixtures/score-good.json or score-bad.json, selected by a header in dev only.
2. Validate the response against the Pydantic contract model before returning.
3. Simulated latency (configurable) to exercise the A5 loading state.
4. A contract test that the real implementation (P23) will also have to pass.

Done when
- The contract test passes against the mock and is reusable against the real service.

---

# M2 — GOP scorer

### P20 — speech-service runtime
Depends on: P04, P17 · Revise before running: YES — paste BENCH.md (threads, int8 verdict)

```text
Task: real model runtime in services/speech with no torch dependency.

Do
1. Dependencies: onnxruntime, numpy, soundfile, and ffmpeg in the image for decoding.
2. Audio input: accept webm/opus, mp4/aac (iOS Safari) and wav. Decode to 16 kHz mono
   float32. Reject clips > 15 s or < 0.3 s of speech with messageKeys.
3. Energy-based VAD trim of leading/trailing silence.
4. Model session loaded once at startup with the thread count from BENCH.md; warmup
   inference before readyz turns green.
5. A bounded asyncio semaphore with the concurrency from BENCH.md. When the queue is
   full, return 503 with Retry-After instead of degrading latency for everyone.
6. Model weights are fetched at build time from a pinned revision, checksum
   verified.

Done when
- Integration test: decode an iOS-recorded m4a fixture and a Chrome webm fixture to
  identical-length arrays within 1%.
- Image size and cold-start time are recorded in services/speech/README.md.
```

### P21 — G2P module
Depends on: P03 · Revise before running: no

```text
Task: text → expected espeak token sequence, per word.

Do
1. Move the P03 mapping into services/speech/src/.../phoneset/ with the YAML as data.
2. Tokenise reference text into words, keep original word spans for the UI.
3. Lexicon override file (YAML) for words g2p_en gets wrong, taken from P03's
   REPORT.md.
4. Numbers and contractions: normalise ("I'm", "don't", digits) before G2P; test each.

Done when
- Unit tests for 30 words, including every mismatch fixed in P03.
- Pure Python, under 10 ms per sentence.
```

### P22 — Alignment + GOP module
Depends on: P20, P21 · Revise before running: no

```text
Task: production alignment and GOP.

Do
1. Port spikes/gop/align.py into the service with its tests. Add a word-boundary map
   so each phoneme knows its word.
2. GOP per phoneme as in P02, plus the competitor token and its probability.
3. Deletion detection: a phoneme aligned to a single frame with very low posterior is
   flagged as possibly deleted (final consonants matter for Vietnamese speakers).
4. Small fixture wavs (< 200 KB total) checked into tests/fixtures with expected
   outputs. `make test-speech` must stay under 10 s: load the model once per session
   via a pytest fixture.

Done when
- Regression tests on the P02 files reproduce the spike verdict.
- `time make test-speech` < 10 s on CI.
```

### P23 — Verdicts, feedback table, real /v1/score
Depends on: P22 · Revise before running: no

```text
Task: turn GOP numbers into ScoreResponse and replace the mock.

Do
1. thresholds/v0.yaml: provisional good/ok/bad thresholds (global). Versioned; the
   version string goes into every response.
2. Word score = aggregate of phoneme scores (define and document: mean vs min).
   Overall = length-weighted word mean, scaled 0–100.
3. Feedback table data/feedback.yaml keyed by (expected, substitutedBy) → messageKey.
   Seed it with the Vietnamese-speaker pairs from PLAN-v7 §2: θ→t, ð→d, ʃ→s, æ→e,
   ɪ→iː, final s/z/t/d/k deletion, cluster reduction. Put the Vietnamese messages in
   apps/web/messages/vi.json under pronunciation.fix.*.
4. fixes[]: top 3 by (badness × frequency in the sentence), one per phoneme.
5. Swap the mock for the real pipeline behind the same endpoint. The P17 contract test
   must pass unchanged.

Done when
- The contract test passes against the real service.
- A test proves no Vietnamese text appears in any response.
```

### P24 — Build the G1 minimal-pair set
Depends on: P23, docs/eval-data.md · Revise before running: no

```text
Task: build 200 evaluation items from LibriSpeech by minimal-pair reference
substitution. No recording. Read docs/eval-data.md section G1 first.

Do
1. tools/evaldata/wordpairs.yaml: for each of the 8 error codes, a list of minimal
   pairs (real word, substituted reference) differing in exactly the target phoneme,
   with the phoneme position recorded.
2. tools/evaldata/build_g1.py: search the LibriSpeech index for utterances containing
   a pair's real word; take up to ~12 items per error code, preferring distinct
   speakers; cut the word plus context; emit two items per utterance:
     match     - audio + reference text with the real word
     mismatch  - same audio + reference text with the substituted word
   Selection is deterministic with a recorded seed.
   Record the target word's time span from the word alignment in the manifest. G1
   scoring must constrain phoneme alignment to that span: when the reference contains
   a phoneme the speaker never produced, free alignment over the whole clip lets that
   phoneme drift into neighbouring words. P02 saw exactly this - scoring "took"
   against /theta U k/ placed /theta/ inside the preceding word "and", 120 ms away
   from the real /t/, and named the wrong competitor. Also verify the cut window
   keeps the word's final consonant; the P01 "think" clip lost its /k/, and FIN_DEL
   items would otherwise be false positives.
3. DATA_DIR/derived/g1/manifest.csv: item_id, utterance_id, speaker_id, wav_path,
   error_code, condition, reference_text, target_word, target_phoneme_index.
4. Validation: every item is 16 kHz mono, 0.4-8 s; every mismatch has a match sibling;
   the per-code count table is printed; speaker overlap across codes is reported. Fail
   loudly on a missing sibling.
5. A split file (by utterance_id, 70/30, seed recorded) written next to the manifest,
   so P25 cannot choose its own split.

Done when
- The manifest has ~200 items with the per-code table printed.
- A test asserts no utterance_id appears in both splits.
```

### P25 — Gates G1 and G2 (HARD GATE)
Depends on: P24 · Revise before running: no

```text
Task: fit thresholds and decide phoneme-level vs word-level scoring, using the
minimal-pair set (G1) and an accented-speech set (G2). See PLAN-v7 section 9.1.

Do
1. eval/gop/: use the split file produced by P24 (by utterance_id). Do not recompute
   it.
2. Fit thresholds on train: global first, then per-phoneme offsets only for phonemes
   with at least 30 test examples. Write thresholds/v1.yaml.
3. G1 metrics on test:
     - detection recall: of the mismatch items, how many flag the substituted phoneme;
     - localisation: the flagged phoneme must fall inside the target word's span from
       the manifest. A flag outside that span counts as a MISS, not a detection.
       Report in-span and out-of-span counts separately: a scorer that flags the right
       error in the wrong place is not usable in the product, which tells the learner
       which sound to fix.
     - precision: of all flagged phonemes in mismatch items, how many are the target;
     - false-alarm rate: fraction of phonemes flagged in match items;
     - competitor accuracy: the named competitor equals the phoneme actually produced;
     - per-error-code breakdown (8 rows) — a code below 0.5 recall is named explicitly.
   Gate: recall >= 0.8, precision >= 0.7, false-alarm <= 0.15.
4. G2: repeat the same construction over a Common Voice non-native slice, or use
   L2-ARCTIC's real annotations if access was granted, and report detection recall. If
   neither is under DATA_DIR, write "G2 not run" in the report — do not skip silently
   and do not substitute another number.
5. eval/gop/REPORT.md: both gates, the per-code table, the split seed, and a plain
   statement of what these numbers do and do not show: native English speech,
   constructed reference errors, no Vietnamese-learner validation.
6. Verdict: phoneme level if G1 passes. Otherwise set level="word" in responses and
   record the decision.
7. `make eval-gop` reproduces the report from the frozen dataset.

Rules
- Do not tune thresholds against the test split. If you are tempted, that is the
  finding: report it.
- Do not report a Pearson r against human ratings. There are no human ratings here.
- Do not describe the set as "learner errors". They are reference substitutions.

Done when
- REPORT.md states the G1 verdict with the numbers and the per-code table.
- CI runs a fast subset and fails if recall drops more than 0.05 below the recorded
  value.
```

---

# M3 — Launch (standalone scorer)

### P30 — Recording flow A2, A3, A4, A9
Depends on: P16, P17 · Revise before running: YES — paste the A2/A3/A4 designs

```text
Task: sentence picker, ready and recording screens, plus mic error states.

Do
1. A2: five sentences from a JSON file (sentences from real VOA items, with source
   URLs), each with IPA rendered through <Ipa>.
2. Recorder hook: MediaRecorder with mime-type negotiation (webm/opus, then mp4 for
   iOS Safari), a 15 s hard cap, AnalyserNode waveform, and a stop button.
3. A9 states: permission denied, no device, insecure context, network error. Each
   state has an instruction in vi.json, including iOS Safari settings steps.
4. All copy lives in vi.json. The 72 px mic button, touch targets ≥ 44 px.

Done when
- Playwright with a fake media stream records and reaches the upload call.
- Component tests cover each A9 state.
```

### P31 — Scoring and result A5, A6
Depends on: P30 · Revise before running: YES — paste the A6 design

```text
Task: the most important screen.

Do
1. A5 skeleton while the score request runs; a timeout and retry path.
2. A6 exactly per design: score ring (tabular numerals), per-word verdicts with
   colour + wavy underline + label, a phoneme chip strip with a tap-for-detail sheet,
   at most 3 fix cards with reference audio, "Thử lại" and "Chia sẻ kết quả".
3. level="word" responses hide the phoneme strip (the P25 fallback).
3b. While G3 is open, the result screen carries a small "beta" marker and the score
   ring is framed as sounds to work on, not as a measurement of the learner. The
   wording is in vi.json; keep it short and non-apologetic.
4. Accessibility: verdicts readable by a screen reader; colour is never the only
   channel (test with a grayscale snapshot).

Done when
- Visual tests for good, bad and word-level fixtures.
- A 3-second comprehension check is documented in the PR: which sound is wrong is
  visible without scrolling at 390x844.
```

### P32 — Landing, share card, auth modal A1, A7, A8
Depends on: P31, P14 · Revise before running: no

```text
Task: acquisition and sign-up loop.

Do
1. A1 landing with one CTA to try without signing up.
2. A7 share card: next/og ImageResponse at 1200x630, from a signed attempt id (no
   audio, no PII in the URL). Must stay legible at 300 px wide. OG meta on the
   share page.
3. A8 sign-up/login modal shown only after a result exists, wired to P14. The
   anonymous attempt is claimed after sign-up (next prompt handles the backend).

Done when
- Share URL renders an OG image in a test, and the page passes Facebook's OG tag
  requirements (og:title, og:image, og:image:width/height).
```

### P33 — Anonymous attempts, consent, claim
Depends on: P32, P15 · Revise before running: no

```text
Task: store attempts safely and turn anonymous users into accounts.

Do
1. Anonymous session id (httpOnly cookie). Attempts stored with score JSON always;
   audio stored in R2 only if the user ticked a separate, unticked-by-default
   consent box ("cho phép dùng bản ghi để cải thiện chấm điểm"). This consented audio
   is the only route to gate G3 (PLAN-v7 §9.1), so the consent text must cover
   evaluation use explicitly.
2. R2 keys by attempt id, lifecycle rule to delete non-consented temp audio after
   24 h. Consent record: text version, timestamp, attempt id.
3. On UserRegistered, a consumer claims attempts of the anonymous session.
4. Data deletion endpoint: deletes attempts and audio for a user.

Done when
- Tests: no audio persisted without consent; claim is idempotent; deletion removes R2
  objects (fake R2 in tests).
```

### P34 — Analytics, privacy, abuse protection
Depends on: P33 · Revise before running: no

```text
Task: launch hygiene.

Do
1. PostHog events: landing_view, record_start, record_done, score_shown, share_click,
   signup_done, with no audio or text content. Funnel dashboard definition in docs.
2. Privacy policy page in Vietnamese (in vi.json), covering audio, consent, retention,
   deletion, processors (Cloudflare, PostHog, the LLM provider).
3. Turnstile on the anonymous score endpoint; per-IP and per-session rate limits;
   the P20 semaphore is the last line.

Done when
- A load test (locust or k6) at 2x the BENCH.md capacity shows 503s, not timeouts.
```

### P35 — Deploy
Depends on: P34 · Revise before running: YES — confirm the VPS (Oracle Free or Hetzner)

```text
Task: first production deploy for core + speech + web.

Do
1. Decide how to host the web app: self-hosted Next.js on the VPS, or Cloudflare via
   the OpenNext adapter. Evaluate against: next/og support, cold start, cost, and
   deploy complexity. Record the choice in a new ADR (next free number).
2. Docker images for core and speech, Compose for production with restart policies
   and resource limits (speech isolated so it can crash alone).
3. Caddy for TLS, Cloudflare DNS, R2 bucket, secrets via env files not in git.
4. Mongo backups: nightly mongodump to R2 with a restore test.
5. A deploy runbook in docs/runbook.md.

Done when
- The public URL scores a recording end to end.
- A restore from last night's backup is proven into a scratch database.

---

# M4 — Course engine (vertical slice: level 4, unit 4)

### P40 — Content model + unit 4 seed
Depends on: P15, P06 · Revise before running: YES — paste the VOA item chosen for unit 4

```text
Task: content context entities and a hand-authored unit 4.

Do
1. Beanie documents per PLAN-v7 §5.1: Level, Unit, Lesson, Exercise, Learnable
   (word | sentence | grammarPoint | phoneme), Source (url, byline, license_ok,
   audio key). Every Learnable carries cefrLevel, topicIds, origin.
2. Validation rules in code, not comments: a Unit has exactly 12 targetVocab and 1
   targetGrammar; every sentence Learnable references a Source or a Tatoeba id with
   attribution; English text with origin other than corpus is rejected.
3. seed/unit-04/: JSON for the unit from the real VOA item, 12 words with corpus
   example sentences, 1 grammar point with a Vietnamese explanation key in vi.json.
4. Read endpoints: GET /v1/levels, /v1/units/{id}, /v1/lessons/{id}.

Done when
- `make seed` loads unit 4; validation tests reject a unit with 11 words and a
  generated English sentence.
```

### P41 — Exercise engine (backend)
Depends on: P40 · Revise before running: no

```text
Task: deterministic answer checking for all MVP exercise types.

Do
1. A registry keyed by exercise type. Each type defines its payload schema (in
   packages/contracts), its answer schema, and a pure check(payload, answer) ->
   Result(correct, expected, feedbackKey).
2. Types: listen_select_meaning, listen_select_word, match_pairs, word_bank_sentence,
   word_bank_translate (accepted-answer list), fill_blank (with accepted variants),
   dictation (normalised token match: case, punctuation, contractions), read_aloud
   and listen_repeat (delegate to speech-service; pass if overall ≥ threshold from
   config).
3. POST /v1/exercises/{id}/answers stores the answer and emits ExerciseAnswered via
   the outbox.
4. Lesson generator: builds a 10–15 exercise lesson from a lesson spec, mixing types,
   with a fixed seed per learner-lesson so reloads show the same sequence.

Done when
- Property-based tests (hypothesis) for dictation normalisation and word-bank checks.
- One test per type for correct, wrong, and malformed answers.
```

### P42 — Learning context: progress and unlocks
Depends on: P41 · Revise before running: no

```text
Task: learner progress as a read model built from events.

Do
1. Consume ExerciseAnswered and LessonCompleted. Keep progress per learner × lesson
   and × unit.
2. Unlock rules from PLAN-v7 §3.3: next lesson unlocks on completion; units unlock
   in order; no score threshold.
3. GET /v1/me/path returns the level/unit/lesson tree with states
   (completed | current | available | locked).
4. Rebuild command: replay the stream into a fresh read model and diff against the
   live one.

Done when
- Replay produces an identical read model in a test.
```

### P43 — FSRS review
Depends on: P42 · Revise before running: no

```text
Task: spaced repetition with the maintained py-fsrs library, not a hand-rolled one.

Do
1. Pin the current py-fsrs release. One card per learner × learnable, created only
   when the learnable's lesson (L1–L4) is completed.
2. Map exercise outcomes to ratings: wrong → Again; correct after a hint → Hard;
   correct → Good; correct and fast on a recognition type → Easy. Document the
   mapping; it is a product decision.
3. GET /v1/me/review builds a review lesson from due cards through the P41 lesson
   generator.
4. Store the full review log for future parameter optimisation.

Done when
- A time-travel test (injected clock) shows intervals growing after Good ratings and
  resetting after Again.
```

### P44 — Gamification: XP, daily goal, streak
Depends on: P42 · Revise before running: no

```text
Task: the three mechanics from PLAN-v7 §6, nothing more.

Do
1. XP per completed lesson (10) plus a perfect-lesson bonus (5); review lessons
   count.
2. Daily goal (default 20 XP, user-settable 10/20/30/50).
3. Streak: a day counts when the daily goal is met, with the day boundary in
   Asia/Ho_Chi_Minh. One streak freeze, earned back after 7 streak days.
4. Idempotent by eventId; recomputable from events.

Done when
- Tests around midnight in Asia/Ho_Chi_Minh, freeze consumption, and duplicate events.
```

### P45 — Lesson player B20 + first four exercise types
Depends on: P41, P16 · Revise before running: YES — paste the B20 design

```text
Task: the shell every lesson and review renders in.

Do
1. B20 per design: close, progress bar, exercise slot, check button, feedback sheet
   (correct / wrong with a specific Vietnamese explanation). No hearts.
2. Exercise components: listen_select_meaning, listen_select_word, match_pairs,
   fill_blank. Each is a pure component: (payload, onAnswer).
3. Audio playback with a 0.8x replay; preload the next exercise's audio.
4. Optimistic answer submit with retry; progress survives a reload (server state
   via TanStack Query).

Done when
- Playwright completes a 4-exercise fixture lesson at 390 px.
```

### P46 — Remaining exercise types + speaking inside lessons
Depends on: P45, P23 · Revise before running: no

```text
Task: word_bank_sentence, word_bank_translate, dictation, read_aloud, listen_repeat.

Do
1. Word bank with tap-to-place (no drag required on mobile).
2. Dictation with a Vietnamese on-screen hint about spelling vs listening errors.
3. read_aloud and listen_repeat reuse the P30 recorder and render a compact A6 in the
   feedback sheet.

Done when
- Playwright completes a lesson containing all 9 types with fake media.
```

### P47 — Path B14, unit B14b, lesson complete B21, streak B22
Depends on: P45, P44 · Revise before running: YES — paste designs

```text
Task: navigation and motivation screens.

Do
1. B14 path from GET /v1/me/path, B14b unit with 6 lessons and states.
2. B21 lesson complete: XP gained, daily goal ring, streak state (400 ms celebration
   motion; emoji allowed only here).
3. B22 streak and daily goal settings.

Done when
- States are distinguishable in a grayscale snapshot test.
```

### P48 — Vocab card B16, grammar B17, review B23, end-to-end
Depends on: P47, P43 · Revise before running: YES — paste designs

```text
Task: close the vertical slice.

Do
1. B16 vocabulary card with the corpus example sentence and Tatoeba attribution
   where applicable.
2. B17 grammar explainer: contrastive Vietnamese explanation, lines quoted from the
   unit source with audio.
3. B23 review session in the B20 shell.
4. Playwright end-to-end: register → path → complete unit 4 lessons 1–5 → next day
   (clock override) → review queue is non-empty.

Done when
- The M4 exit criterion in PLAN-v7 passes as that Playwright test.
```

---

# M5 — Content pipeline + level 4

### P50 — Worker + VOA fetcher with licensing filter
Depends on: P06, P40 · Revise before running: no

```text
Task: services/worker (arq) and ingestion of selected VOA items.

Do
1. Worker process with its own settings, OTel, and a job registry.
2. fetch_source job: download the text and audio of one inventory row, re-check the
   license filter (VOA byline, not wire content, no third-party media), store a
   Source with raw HTML hash, cleaned text, and audio in R2.
3. Cleaning: NFC, strip boilerplate, sentence split, keep paragraph offsets.

Done when
- Tests with saved HTML fixtures: a wire-service article is rejected, a VOA-staff one
  accepted.
```

### P51 — Level scoring, dedup, sentence picker
Depends on: P50 · Revise before running: no

```text
Task: turn sources into candidate learnables.

Do
1. Lemmatise with spaCy en_core_web_sm; a frequency band per lemma from NGSL and
   Oxford lists.
2. Sentence CEFR estimate: length + lemma frequency bands + grammar features.
   Document it as a heuristic, not a model; calibrate later if needed.
3. Tatoeba en–vi import with attribution fields.
4. Dedup: MinHash for near-duplicates, then bge-m3 cosine for paraphrases.
5. Sentence picker: for each target lemma, rank corpus sentences by level fit,
   length, and diversity. Store the top 3.
6. Cross-lingual check with bge-m3 on Tatoeba pairs, validated on 200 labelled pairs;
   report precision at the chosen threshold (PLAN-v7 §5.5).

Done when
- A report for unit 4: 12 lemmas × 3 sentences, with level fit, and the bge-m3
  validation numbers.
```

### P52 — ai-gateway
Depends on: P13 · Revise before running: YES — confirm providers and models

```text
Task: one place for every LLM call.

Do
1. services/ai-gateway: OpenAI-compatible client abstraction with a primary and a
   fallback provider, timeouts, and retry on 429/5xx with jitter.
2. Prompts as versioned files in prompts/<task>/<version>.md with a front-matter
   schema reference. The prompt version is recorded on every output.
3. Structured output: responses parsed into Pydantic models; on validation failure,
   one repair retry, then fail.
4. OTel gen_ai.* spans (model, tokens in/out, cost), Langfuse tracing, a cost
   ledger per task per day, and a hard daily spend cap.
5. Batch mode for offline jobs where the provider supports it.

Done when
- Tests with a fake provider: fallback on 5xx, spend cap stops calls, invalid JSON
  triggers exactly one repair.
```

### P53 — Scaffolding generators + validators
Depends on: P51, P52 · Revise before running: no

```text
Task: LLM-generated scaffolding only (ADR-0006).

Do
1. Tasks and prompts: distractors (same POS, same level, plausible, not synonyms),
   Vietnamese glosses, contrastive grammar explanations (Vietnamese), IELTS Part 1
   style questions about the unit topic.
2. Validators per task:
     distractors — not equal to the answer, not a synonym (bge-m3 similarity cap),
                   same POS via spaCy;
     glosses     — non-empty, length cap;
     questions   — English, level-appropriate by the P51 heuristic, answerable with
                   the unit vocabulary;
     all         — the output may not introduce new English source sentences.
3. Golden set of 20 hand-checked items per task; `make eval-content` reports pass
   rates.

Done when
- Eval report for unit 4 with pass rates per task and a sample of rejects.
```

### P54 — Template expansion, TTS batch, review tool
Depends on: P53, P05 · Revise before running: no

```text
Task: turn learnables into exercises with audio, and review them.

Do
1. Templates per exercise type that generate exercises from learnables
   deterministically.
2. Kokoro batch job: audio for words, sentences, questions, dialogue lines where no
   VOA audio exists, at 0.8x and 1.0x; content-hash keys in R2 so reruns are free.
3. Review CLI (or a small admin page): 100% of grammar explanations, a random 10% of
   exercises, approve/reject with reason; rejected items go back to generation.

Done when
- Unit 4 fully rebuilt by the pipeline instead of the hand seed, and the P48
  end-to-end test still passes.
```

### P55 — Build units 1–8
Depends on: P54 · Revise before running: YES — paste the final topic list from the inventory

```text
Task: run the pipeline for all level 4 units and report.

Do
1. Run per unit, review, fix validator gaps found along the way (as code, with tests).
2. docs/content-report-level4.md: per unit source, words, grammar point, review
   rejection rate, cost.

Done when
- 8 units pass validation and review; total generation cost is recorded.
```

### P56 — Streak reminder email
Depends on: P44 · Revise before running: no

```text
Task: one daily reminder email for learners at risk of losing a streak.

Do
1. Pick a transactional email provider with a free tier; record the choice in the
   HANDOFF (not an ADR unless it costs money).
2. Scheduled worker job at 19:00 Asia/Ho_Chi_Minh; opt-in, one-click unsubscribe.
3. Copy in vi.json.

Done when
- Tests for scheduling and unsubscribe; no email to users who met today's goal.
```

---

# M6 — Speaking (lesson 6)

### P60 — STT adapter
Depends on: P20 · Revise before running: no

```text
Task: transcripts with word timestamps and confidence, for transcription only.

Do
1. Interface transcribe(audio) -> words[{text, startMs, endMs, confidence}].
2. Implementations: Moonshine (local dev) and the Groq Whisper API (prod). Verify
   the API returns word-level timestamps; if confidence is unavailable, derive a
   proxy and document it.
3. Measure WER on 50 Vietnamese-accented clips from the calibration set; record it in
   eval/stt/REPORT.md.
4. A guard test: the GOP code path must not import the STT module.

Done when
- WER report exists; the import guard test passes.
```

### P61 — Fluency metrics
Depends on: P60 · Revise before running: no

```text
Task: words per minute, silence ratio, hesitation count, longest fluent run.

Do
1. Pure functions over word timestamps. Filled pauses (uh, um, ờ, à) and pauses
   > 500 ms count as hesitations.
2. Map to a 0–100 score with documented bands; the band values are config.

Done when
- Unit tests on synthetic timelines, including an all-silence clip.
```

### P62 — Task completion
Depends on: P60, P55 · Revise before running: no

```text
Task: did the learner use the unit's vocabulary and grammar?

Do
1. Lemma match of the transcript against targetVocab (inflections count).
2. spaCy Matcher/DependencyMatcher patterns per grammar point, stored with the
   grammar Learnable, for the 8 level 4 points.
3. Label 100 transcripts (from P60 clips plus written variants) with used/unused per
   target; eval/task/REPORT.md with precision and recall. Gate: precision ≥ 0.9.

Done when
- The gate passes, or the report lists which patterns fail and they are disabled
  (not shown to learners) until fixed.
```

### P63 — Free-speech GOP with confidence gating
Depends on: P60, P25 · Revise before running: no

```text
Task: pronunciation scores on free answers without trusting STT errors.

Do
1. Reference text = STT transcript. Score only words with confidence ≥ threshold,
   plus target vocabulary words.
2. Choose the threshold from the P60 WER data.
3. Eval on 100 labelled free-speech clips: Pearson r. Gate r ≥ 0.5; otherwise the
   pronunciation axis is hidden for free speech (contract flag).

Done when
- eval/gop-free/REPORT.md states the verdict with numbers.
```

### P64 — Lesson 6 flow: B24 + B19
Depends on: P61, P62, P63 · Revise before running: YES — paste designs

```text
Task: the unit goal.

Do
1. POST /v1/speaking/answers: runs STT, fluency, task completion, and gated GOP, and
   returns a SpeakingResult contract (add it to packages/contracts first).
2. B24 speaking question screen and B19 speaking result screen per design. Hidden axes
   (failed gates) are omitted, not shown as zero.
3. Lesson 6 counts as completed when all questions are answered or skipped.

Done when
- Playwright completes lesson 6 with fixture audio.
```

---

# M7 — Eval + production

### P70 — Unified eval harness
Depends on: P25, P53, P60–P63 · Revise before running: no

```text
Task: `make eval` runs every gate from PLAN-v7 §9 and writes one report.

Do
1. A runner that executes each eval, compares with recorded baselines, and writes
   eval/REPORT.md with a pass/fail table.
2. CI: fast subset on every PR; full run nightly and on release tags.
3. Any LLM judge added later must first report Cohen's κ vs human labels (≥ 0.6)
   before it may gate CI.

Done when
- A deliberately degraded threshold file fails the CI job.
```

### P71 — Observability
Depends on: P70 · Revise before running: YES — confirm budget for Grafana Cloud free tier vs self-hosting

```text
Task: traces, metrics, logs, and three dashboards.

Do
1. OTel collector; choose the Grafana Cloud free tier or self-hosted (VPS memory is
   the constraint) and record why.
2. Dashboards: scoring latency p50/p95 and 503 rate; learner funnel (from PostHog);
   LLM cost per day (from the cost ledger).
3. Alerts: speech-service down, p95 > 3 s for 10 min, daily LLM spend > cap × 0.8.

Done when
- A synthetic failure fires an alert in a test run.
```

### P72 — k3s + CD
Depends on: P71 · Revise before running: YES — confirm the prod node

```text
Task: move production from Compose to k3s.

Do
1. Manifests (Kustomize) for core, speech, web (if self-hosted), Mongo (or keep
   Mongo outside k3s with a reason), Redis.
2. Resource requests/limits from BENCH.md; speech gets a PodDisruptionBudget and a
   readiness probe on warmup.
3. GitHub Actions CD: build, push, deploy on tag, automated rollback on failed
   readiness.
4. Update docs/runbook.md.

Done when
- A tag deploys, and a broken image rolls back automatically.
```

### P73 — Split worker and ai-gateway into their own processes
Depends on: P72 · Revise before running: no

```text
Task: reach the 4-process layout from ADR-0001.

Do
1. Deploy worker and ai-gateway separately; confirm no shared in-process state with
   core.
2. Chaos test: kill each process in turn and show the others keep serving (realtime
   scoring unaffected by a dead worker).

Done when
- The chaos test results are recorded in docs/runbook.md.
```

### P74 — Portfolio packaging
Depends on: all gates reported · Revise before running: no

```text
Task: make the work legible to an AI Engineer hiring manager.

Do
1. README: problem, architecture diagram (Mermaid), and the PLAN-v7 §14 portfolio map
   filled with real numbers from eval/REPORT.md. Every claim links to a report.
1b. A "Limits of the evaluation" section: G1 is native English speech with constructed
   reference errors, G2 is non-Vietnamese accented speech, G3 is open and what would
   close it. Write it plainly; an honest limits section is stronger than an
   unqualified number.
2. docs/adr/README.md index.
3. A 3-minute demo video script: recording → phoneme error → Vietnamese fix → unit
   lesson → speaking result.
4. Two blog post outlines: "Why not Whisper for pronunciation scoring" and "Serving
   wav2vec2 on a $0 CPU VPS".
5. Cohort chart from PostHog (D1/D7).

Done when
- A reviewer can verify every number in the README from a file in the repo.
