# HANDOFF

Last updated: 2026-09-30

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
- **P05 done (listening pending).** `spikes/tts/`: Kokoro-82M, VOA sentence at three
  speeds plus a 6-turn dialogue; RTF 0.35-0.41 at 4 threads. Fill `CHECKLIST.md`.
- **P06 built, inventory partial.** `tools/voa_inventory/`; `docs/voa-inventory.md` covers
  600 of 67,337 pages (73 usable; 96 of 169 audio+text pages fail the licence filter).

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
- P04: rerun `spikes/gop/onnx/` on the real VPS (commands in BENCH.md); the capacity
  numbers above are for this laptop.
- P06: crawl cache has ~6,500 pages, idle since 15:14. Resume `VOA_CONTACT_EMAIL=... make
  voa-crawl ARGS="--limit 100000"`, then `make voa-report`; commit `data/`, `docs/`.
- P05: the owner fills in `spikes/tts/CHECKLIST.md` by ear; no quality verdict yet.
