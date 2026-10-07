# HANDOFF

Last updated: 2026-10-07

## Done
- Docs (PLAN-v7, ADR-0001/0004/0006, design-system, BUILD-PROMPTS, eval-data); P10 scaffold. **P01/P02 done, GATE G0 PASS.** `spikes/gop/`: θ|correct +3.89, t|substituted −5.71.
- **P03/P21 done.** ARPAbet→espeak table (93.0%, `make check-phoneset`) now in `sonari_speech.phoneset`; `.g2p` gives per-word tokens.
- **P04 done.** `spikes/gop/onnx/BENCH.md`: int8 keeps G0 (355 vs 1264 MB); 280 ms p50, laptop.
- **P05 done (listening pending).** `spikes/tts/`: Kokoro-82M, 3 speeds + dialogue, RTF 0.35-0.41.
- **P06 tagger: `phrase`** (F0.5 0.36 vs bge-m3 0.35; 100 pages, one labeller). Tag counts
  are leads, not supply; pre-fix counts void. 34/100 usable lv-4 pages are `language_learning`.
- **Level 4 units decided (PLAN 4.1/4.2).** 8 corpus-backed units + Unit 0 (speaking-only Part 1 starter, no passage); Films and TV is the one reserve. Record: `docs/level4-units-proposal.md`.
- **P11 done.** `compose.yaml`, `infra/mongo/`: Mongo `rs0` + Redis. `make infra && make test-core`. New clone: `make setup` (git hooks).
- **P13 done** (#19): `sonari_core.shared`, 5 contexts, `/readyz`, OTel; `make check-imports` fails on cross-context imports. P12 skipped.
- **P14 done** (#20): `/v1/auth`, refresh rotation, Turnstile, rate limit. Deploy: uvicorn `--proxy-headers`.
- **P15 done** (ADR-0007): `shared/outbox.py`, `shared/consumer.py`. CI runs its live tests (#28: `make infra`; speech uses vendored cmudict); with `CI` set a missing service fails, not skips.
- **Conflict markers now fail pre-commit and CI** (`check-merge-conflict --assume-in-merge`). A clean merge still skips pre-commit hooks (backlog).
- **P20 done** (int8): `sonari_speech.runtime`. Model on Hugging Face (`models.yaml` `url` list; R2 mirror TODO); CI skips its 4 real-model tests.
- **Passages classified** (`make voa-classify`, `docs/reports/voa-classify.md`; measurement only, no LLM, no corpus written). Of the 724: 322 teach English, 370 are an explainer or news item, 9 dialogue scripts. 50 passages read by hand (one labeller, the assistant; not held out): usable type wrong 2 of 50. **Safety stems narrowed** (`docs/reports/voa-safety-stems.md`; disaster flagged only with casualties): no flag on **257** of the 370 (default rule; strict 295, loose 170; first run 240), thinnest unit Sport (16). Every flag removed was read: 0 wrong by default, 2 wrong under strict. `president`, `government` and `democrat` are literal again (the narrow forms fitted passages already read). Decide next: which flag rule, and whether English-teaching passages feed anything.
- **Source ingest done** (ADR-0010): `content.sources` holds the 724 trimmed passages; `make ingest-sources` is idempotent (`_id` = `voa:<article>@<rules_version>`); a re-trim adds a version and flips `current`, never overwrites. 6 MiB, indexes 84+88 KiB, cold ingest 3 s, no-op 1.5 s. Docker is off in this WSL distro: live tests ran on a user-space mongod 7.0 `rs0`; CI runs `make infra`. `make ingest-sources ARGS=--dry-run` forecasts a run from reads alone (no write, no index; exit 1 on a conflict; `superseded` covers a re-trim and a rollback). **The service enforces ADR-0008 where a file enters** (`content/trim_rules.py`): cap 5% whatever the file declares, window 250-1,200 on `text`, `fk` < 7, and `original_words`, `removed_words`, `removed_share` derived from the lines (all 724 recompute exactly: nothing changed, re-ingest = 724 unchanged, 0 conflicts). `scripts/tests/test_adr_0008_*drift.py` fail when `tools/voa_corpus`, the service or the ADR's text disagree; `make test-scripts` pins pydantic and beanie (and their deps) to the core lock via `scripts/locked_pins.py`. A rule that tightens later also fails stored versions on read (backlog).
- **`POST /v1/score` done** (P22 + P23's endpoint; no feedback table, no overall score): `sonari_speech.scoring`, contract `packages/contracts/schema/score-response.schema.json`. Whole-sentence alignment, P02's GOP, v0 threshold `gop > 0` **UNCALIBRATED**. G0 clips (local only, `pytest -rP tests/scoring/test_g0_clips.py`): good.wav 9/9; "tink" → /t/ wrong, heard θ. 12-core laptop: 2.9 s clip 489 ms p50, 10.8 s 2.6 s (model ≈ all; align+GOP ≤ 16 ms); burst 7 p95 1.26 s, 12 (= slots) 2.08 s, over BENCH's 2 s. Dockerfile now fetches cmudict: not built (Docker off).
- **Vietnamese feedback done** (P23's table): every wrong phoneme in `/v1/score` carries `feedback {messageKey, params{expected,heard,word}}`; the client renders `<key>.why` and `.how` from `vi.json` `pronunciation.fix.*`. Rules and evidence: `scoring/feedback.yaml` (pair, then final consonant / cluster, then `generic`, which claims no cause). **Needs a native reader before launch: all 12 messages.** Pairs with no source: θ→s, ð→d, ʃ→s (the rest rest on 8 sources, only Pham 2023 read in full; n/l is a Vietnamese-dialect study; æ→ɛ is one speaker). Position rules cannot know a sound was dropped (`heard` is noise then), so the copy says "unclear", not "dropped". Not covered: ð→dʒ, s→ʃ, ɪ/iː, stress.

## Notes for G1 (P24/P25)
- One reference token per phone gives false errors: bad.wav "and" read æ vs weak-form ə (gop −4.9); likewise `ɐ ᵻ ɪ`, the flap, syllabic `əl` (`phoneset/REPORT.md`).
- `tools/evaldata/ctc_align.py` and `spikes/gop/align.py` are still copies of `scoring/align.py`.

## Next (one per session; prompts in `docs/prompts/BUILD-PROMPTS.md`)
1. Design A6 → P12 contracts (ScoreResponse exists; P12 owns codegen). 2. P22 rest: deletion flag. 3. P23 rest: thresholds per phoneme, overall score, fixes[] (top 3). 4. P40: Learnables and exercises store the pinned `Source._id`, never "current" (ADR-0010); P50 still reads each chosen passage.

## Blockers
- P04: rerun `spikes/gop/onnx/` on the real VPS (BENCH.md); numbers above are the laptop's.
- P06: crawl done (47,854 of 67,337 pages). `make voa-corpus` (`docs/reports/voa-corpus.md`): **48 passages usable as-is at level 4, 724 with a cut of at most 5%** (ADR-0008 §2; 413 of them outside English-teaching and fiction programmes), about 409 free of missed frame (CI 330-484; the MVP needs ~50); every unit has >= 28 passages by crude tags, but 16 to 38 once type and the default safety flag apply (voa-safety-stems.md). Rules: closed lists and closed grammars only, no open slots. Precision: 0 wrong in the 1,273 lines removed, 0 in a random 300 + 150 (`docs/reports/voa-trim-corpus.md`). **Trimming is done:** `make voa-trim` writes `~/sonari-trimmed/voa/` (724 passages, 5.9 MB, outside the repo, regenerable; `--cap` changes the cap). Recall work stopped. `make voa-evaluate voa-report` still to run.
- Stale after the unit rewrite (not edited; out of scope): BUILD-PROMPTS P40-P55 say "unit 4"
  and "units 1-8" (the hand-built slice is now unit 3, food; add Unit 0); design-system.md
  §5 uses "Đồ ăn & nhà hàng"; `tools/voa_inventory/topics.yaml` and the report still carry
  the old 8 topics. ADR-0006 steps 2-3 assume a passage; Unit 0 has none (PLAN 4.2).
- P05: owner fills `spikes/tts/CHECKLIST.md` by ear; no quality verdict yet.
