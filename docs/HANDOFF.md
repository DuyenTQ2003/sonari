# HANDOFF

Last updated: 2026-10-02

## Done
- Docs (PLAN-v7, ADR-0001/0004/0006, design-system, BUILD-PROMPTS, eval-data); P10 scaffold.
- **P01/P02 done, GATE G0 PASS.** `spikes/gop/`: θ|correct +3.89, t|substituted −5.71.
- **P03 done.** `spikes/gop/phoneset/`: ARPAbet→espeak table; 200 NGSL words vs espeak-ng
  88.0% strict, 93.0% after fold rules. `make check-phoneset`.
- **P04 done.** `spikes/gop/onnx/BENCH.md`: fp32 matches torch; int8 (355 vs 1264 MB) keeps
  the G0 verdict. 3 s p50 at 1/2/4 threads: fp32 1336/797/568 ms, int8 609/372/280 ms (laptop).
- **P05 done (listening pending).** `spikes/tts/`: Kokoro-82M, 3 speeds + dialogue, RTF 0.35-0.41.
- **P06 tagger: `phrase`** (F0.5 0.36 vs bge-m3 0.35; 100 pages, one labeller). Plan-topic
  P 0.37, R 0.32: tag counts are leads, not supply. Pre-fix counts void. 34/100 usable lv-4
  pages are `language_learning`.
- **Level 4 units decided (PLAN 4.1/4.2).** 8 corpus-backed units + Unit 0, a speaking-only
  Part 1 starter (hometown, home, family; no passage). Films and TV is the one reserve; a
  second failed unit at M5 leaves 7. Record: `docs/level4-units-proposal.md`.
- **P11 done.** `compose.yaml`, `infra/mongo/`: Mongo 7 `rs0` with auth, Redis 7 AOF, 7 context
  DBs, users `core` and `speech` only. `make infra && make test-core` (10 pass); `make dev` blocks.

## Notes for G1 (P24/P25)
- Whole-clip alignment lets an absent phoneme drift into context (bad.wav: θ landed in
  "and"); constrain alignment to the word span. Pick fp32 or int8 BEFORE calibrating.
- One reference token per phone gives false errors on unstressed vowels (`ə ɐ ᵻ ɪ`), the
  US flap and syllabic `əl` (`phoneset/REPORT.md`). Untested on model output.
- `spikes/gop/align.py` copies `tools/evaldata/ctc_align.py`; merge at P21/P22.

## Next (one per session; prompts in `docs/prompts/BUILD-PROMPTS.md`)
1. Design A6 → P12 contracts. 2. P20 speech runtime (int8 vs fp32 first).

## Blockers
- P04: rerun `spikes/gop/onnx/` on the real VPS (BENCH.md); numbers above are the laptop's.
- P06: crawl still running (17%); then `make voa-evaluate voa-report`.
- Stale after the unit rewrite (not edited; out of scope): BUILD-PROMPTS P40-P55 say "unit 4"
  and "units 1-8" (the hand-built slice is now unit 3, food; add Unit 0); design-system.md
  §5 uses "Đồ ăn & nhà hàng"; `tools/voa_inventory/topics.yaml` and the report still carry
  the old 8 topics. ADR-0006 steps 2-3 assume a passage; Unit 0 has none (PLAN 4.2).
- P05: owner fills `spikes/tts/CHECKLIST.md` by ear; no quality verdict yet.
