# HANDOFF

Last updated: 2026-09-29

## Done
- Docs: PLAN-v7, CLAUDE.md, ADR-0001/0004/0006, design-system (v7), BUILD-PROMPTS,
  eval-data. P10 scaffold (core + speech, Makefile, pre-commit, CI).
- Typecheck target fixed + CI/Makefile guard test (#1). ADR-0001 and ADR-0004 restored (#4).
- **P01 done, both clips PASS.** `tools/evaldata/` fetches LibriSpeech dev-clean
  (md5, resumable), indexes it (parquet), and builds the G0 pair by script: "think" vs
  "took", same speaker (1993). wav2vec2-lv-60-espeak decodes θ in good.wav (max P 0.94)
  and t in bad.wav (max P 0.96); cross posteriors < 0.004. See `spikes/gop/RESULTS.md`.
- Root `pyproject.toml` (`sonari-tools`, not a workspace) so `uv run python tools/...`
  works from the repo root. New `make test-tools` (numpy-only) runs in CI.

## Notes for P02
- Word boundaries come from a character CTC aligner (wav2vec2-base-960h) + numpy
  Viterbi in `tools/evaldata/ctc_align.py`. P02 writes its own phoneme aligner in
  `spikes/gop/align.py` as specified; the tools one may be reused as a reference.
- CTC posteriors are spiky: top-5 mean is dominated by blank frames. Score GOP over
  aligned frames, not top-k.

## Next (pick one per session)
Session prompts: `docs/prompts/BUILD-PROMPTS.md`.
1. P02: forced alignment + naive GOP on the G0 pair (HARD GATE).
2. Design A6 → P12 contracts.
3. P11 Compose (ADR-0001 now in the repo).

## Blockers
- P02 (G0) can still invalidate the plan. Do it before large FE/BE investment.
- None for P11.
