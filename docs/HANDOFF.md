# HANDOFF

Last updated: 2026-10-03

## Done
- Docs (PLAN-v7, ADR-0001/0004/0006, design-system, BUILD-PROMPTS, eval-data); P10 scaffold.
- **P01/P02 done, GATE G0 PASS.** `spikes/gop/`: θ|correct +3.89, t|substituted −5.71.
- **P03/P21 done.** ARPAbet→espeak table (93.0%, `make check-phoneset`) now in `sonari_speech.phoneset`; `.g2p` gives per-word tokens.
- **P04 done.** `spikes/gop/onnx/BENCH.md`: int8 keeps G0 (355 vs 1264 MB); 280 ms p50, laptop.
- **P05 done (listening pending).** `spikes/tts/`: Kokoro-82M, 3 speeds + dialogue, RTF 0.35-0.41.
- **P06 tagger: `phrase`** (F0.5 0.36 vs bge-m3 0.35; 100 pages, one labeller). Tag counts
  are leads, not supply; pre-fix counts void. 34/100 usable lv-4 pages are `language_learning`.
- **Level 4 units decided (PLAN 4.1/4.2).** 8 corpus-backed units + Unit 0 (speaking-only Part 1
  starter, no passage); Films and TV is the one reserve. Record: `docs/level4-units-proposal.md`.
- **P11 done.** `compose.yaml`, `infra/mongo/`: Mongo `rs0` + Redis. `make infra && make test-core`. New clone: `make setup` (git hooks).
- **P13 done** (#19): `sonari_core.shared`, 5 contexts, `/readyz`, OTel; `make check-imports` fails on cross-context imports. P12 skipped.
- **P14 done** (#20): `/v1/auth`, refresh rotation, Turnstile, rate limit. Deploy: uvicorn `--proxy-headers`.
- **P15 done** (ADR-0007): `shared/outbox.py`, `shared/consumer.py`. CI runs its live tests (#28: `make infra`; speech uses vendored cmudict); with `CI` set a missing service fails, not skips.
- **Conflict markers now fail pre-commit and CI** (`check-merge-conflict --assume-in-merge`). A clean merge still skips pre-commit hooks (backlog).
- **P20 done** (int8): `sonari_speech.runtime`. Model on Hugging Face (`models.yaml` `url` list; R2 mirror TODO); CI skips its 4 real-model tests.

## Notes for G1 (P24/P25)
- Whole-clip alignment lets an absent phoneme drift into context (bad.wav: θ landed in
  "and"); constrain alignment to the word span. Pick fp32 or int8 BEFORE calibrating.
- One reference token per phone gives false errors on unstressed vowels (`ə ɐ ᵻ ɪ`), the
  US flap and syllabic `əl` (`phoneset/REPORT.md`). Untested on model output.
- `spikes/gop/align.py` copies `tools/evaldata/ctc_align.py`; merge at P22.

## Next (one per session; prompts in `docs/prompts/BUILD-PROMPTS.md`)
1. Design A6 → P12 contracts. 2. P22 alignment + GOP. 3. P17 mock speech. 4. Parser fix for bare-text pages (backlog, +942 passages).

## Blockers
- P04: rerun `spikes/gop/onnx/` on the real VPS (BENCH.md); numbers above are the laptop's.
- P06: crawl done (47,854 of 67,337 pages). `make voa-corpus` measured it: 76 passages usable as-is at level 4, 1,080 if host lines may be cut (`docs/reports/voa-corpus.md`). `make voa-evaluate voa-report` still to run. Text-less pages (`make voa-missing`): the 27,118 are audio/widgets (0 of 40 sampled are articles), but 942 of the 1,768 short pages are articles the parser misses (bare text in `div.wsw`); fix in backlog, `docs/reports/voa-missing-pages.md`.
- Stale after the unit rewrite (not edited; out of scope): BUILD-PROMPTS P40-P55 say "unit 4"
  and "units 1-8" (the hand-built slice is now unit 3, food; add Unit 0); design-system.md
  §5 uses "Đồ ăn & nhà hàng"; `tools/voa_inventory/topics.yaml` and the report still carry
  the old 8 topics. ADR-0006 steps 2-3 assume a passage; Unit 0 has none (PLAN 4.2).
- P05: owner fills `spikes/tts/CHECKLIST.md` by ear; no quality verdict yet.
