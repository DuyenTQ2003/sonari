# HANDOFF

Last updated: 2026-10-04

## Done
- Docs (PLAN-v7, ADR-0001/0004/0006, design-system, BUILD-PROMPTS, eval-data); P10 scaffold.
- **P01/P02 done, GATE G0 PASS.** `spikes/gop/`: θ|correct +3.89, t|substituted −5.71.
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
- **Source ingest done** (ADR-0010): `content.sources` holds the 724 trimmed passages; `make ingest-sources` is idempotent (`_id` = `voa:<article>@<rules_version>`); a re-trim adds a version and flips `current`, never overwrites. 6 MiB, indexes 84+88 KiB, cold ingest 3 s, no-op 1.5 s. Docker is off in this WSL distro: live tests ran on a user-space mongod 7.0 `rs0`; CI runs `make infra`.

## Notes for G1 (P24/P25)
- Whole-clip alignment lets an absent phoneme drift into context (bad.wav: θ landed in
  "and"); constrain alignment to the word span. Pick fp32 or int8 BEFORE calibrating.
- One reference token per phone gives false errors on unstressed vowels (`ə ɐ ᵻ ɪ`), the
  US flap and syllabic `əl` (`phoneset/REPORT.md`). Untested on model output.
- `spikes/gop/align.py` copies `tools/evaldata/ctc_align.py`; merge at P22.

## Next (one per session; prompts in `docs/prompts/BUILD-PROMPTS.md`)
1. Design A6 → P12 contracts. 2. P22 alignment + GOP. 3. P17 mock speech. 4. P40: Learnables and exercises store the pinned `Source._id`, never "current" (ADR-0010); P50 still reads each chosen passage.

## Blockers
- P04: rerun `spikes/gop/onnx/` on the real VPS (BENCH.md); numbers above are the laptop's.
- P06: crawl done (47,854 of 67,337 pages). `make voa-corpus` (`docs/reports/voa-corpus.md`): **48 passages usable as-is at level 4, 724 with a cut of at most 5%** (ADR-0008 §2; 413 of them outside English-teaching and fiction programmes), about 409 free of missed frame (CI 330-484; the MVP needs ~50); every unit has >= 28 usable (crude tags). Rules: closed lists and closed grammars only, no open slots. Precision: 0 wrong in the 1,273 lines removed, 0 in a random 300 + 150 (`docs/reports/voa-trim-corpus.md`). **Trimming is done:** `make voa-trim` writes `~/sonari-trimmed/voa/` (724 passages, 5.9 MB, outside the repo, regenerable; `--cap` changes the cap). Recall work stopped. `make voa-evaluate voa-report` still to run.
- Stale after the unit rewrite (not edited; out of scope): BUILD-PROMPTS P40-P55 say "unit 4"
  and "units 1-8" (the hand-built slice is now unit 3, food; add Unit 0); design-system.md
  §5 uses "Đồ ăn & nhà hàng"; `tools/voa_inventory/topics.yaml` and the report still carry
  the old 8 topics. ADR-0006 steps 2-3 assume a passage; Unit 0 has none (PLAN 4.2).
- P05: owner fills `spikes/tts/CHECKLIST.md` by ear; no quality verdict yet.
