# HANDOFF

Last updated: 2026-10-02

## Done
- Docs: PLAN-v7, CLAUDE.md, ADR-0001/0004/0006, design-system (v7), BUILD-PROMPTS,
  eval-data. P10 scaffold (core + speech, Makefile, pre-commit, CI).
- **P01/P02 done, GATE G0 PASS.** LibriSpeech "think"/"took" pair; numpy CTC Viterbi + naive
  GOP in `spikes/gop/` (θ|correct +3.89, t|substituted −5.71). `make test-tools` in CI.
- **P03 done.** `spikes/gop/phoneset/`: ARPAbet→espeak table (50/50 tokens in vocab).
  200 NGSL words vs espeak-ng: 88.0% strict, 93.0% after fold rules. `make check-phoneset`.
- **P04 done.** `spikes/gop/onnx/BENCH.md`. fp32 ONNX matches torch and the P02 GOP numbers.
  Dynamic int8 (MatMul only, 355 vs 1264 MB) keeps the G0 verdict (max GOP change 0.375).
  3 s clip p50 at 1/2/4 threads: fp32 1336/797/568 ms, int8 609/372/280 ms. Burst under
  2 s p95 on 1/2/4 cores: fp32 1/2/3, int8 2/5/7. **Laptop under WSL2, not the VPS.**
- **P05 done (listening pending).** `spikes/tts/`: Kokoro-82M, 3 speeds + dialogue, RTF 0.35-0.41.
- **P06 tagger: `phrase`** (F0.5 0.36 vs bge-m3 0.35; 100 pages, one labeller). Plan-topic
  P 0.37, R 0.32: tag counts are leads, not supply. Pre-fix counts void. 34/100 usable lv-4
  pages are `language_learning`; `shopping` 0/100 unconfirmed. Units 1/5 per PLAN 4.1 swap.

## Notes for G1 (P24/P25)
- Whole-clip alignment lets an absent phoneme drift into context (bad.wav: θ landed in
  "and"). Constrain alignment to the word span before trusting competitor names.
- Pick fp32 or int8 BEFORE calibrating thresholds; calibrate on the deployed model.
- One reference token per phone gives false errors on unstressed vowels (`ə ɐ ᵻ ɪ`), the
  US flap and syllabic `əl` (see `phoneset/REPORT.md`). Untested on model output.
- `spikes/gop/align.py` copies `tools/evaldata/ctc_align.py`; merge at P21/P22.

## Next (one per session; prompts in `docs/prompts/BUILD-PROMPTS.md`)
1. Design A6 → P12 contracts.
2. P11 Compose (ADR-0001 now in the repo).
3. P20 speech-service runtime (needs the int8 vs fp32 decision from BENCH.md).

## Blockers
- P04: rerun `spikes/gop/onnx/` on the real VPS (BENCH.md); numbers above are the laptop's.
- P06: crawl still running (17%); when done, `make voa-evaluate voa-report`.
- P06/units: owner reads `docs/level4-units-proposal.md` (8 units from the corpus, each 10+
  title-confirmed items; hometown/home/family not covered), then PLAN-v7 4.1 is rewritten.
- P05: owner fills `spikes/tts/CHECKLIST.md` by ear; no quality verdict yet.
