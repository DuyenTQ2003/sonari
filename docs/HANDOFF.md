# HANDOFF

Last updated: 2026-09-30

## Done
- Docs: PLAN-v7, CLAUDE.md, ADR-0001/0004/0006, design-system (v7), BUILD-PROMPTS,
  eval-data. P10 scaffold (core + speech, Makefile, pre-commit, CI).
- Typecheck target fixed + CI/Makefile guard test (#1). ADR-0001 and ADR-0004 restored (#4).
- **P01 done, both clips PASS.** `tools/evaldata/` fetches LibriSpeech dev-clean
  (md5, resumable), indexes it (parquet), and builds the G0 pair by script: "think" vs
  "took", same speaker (1993). wav2vec2-lv-60-espeak decodes θ in good.wav (max P 0.94)
  and t in bad.wav (max P 0.96); cross posteriors < 0.004. See `spikes/gop/RESULTS.md`.
- **P02 done, GATE G0 PASS.** Numpy CTC Viterbi (`spikes/gop/align.py`) + naive GOP
  (`run_gop.py`). good.wav: θ|correct gop +3.89, t|substituted gop −5.71, competitor θ.
- Root `pyproject.toml` (`sonari-tools`, not a workspace) so `uv run python tools/...`
  works from the repo root. New `make test-tools` (numpy-only) runs in CI.
- **P05 done (listening pending).** `spikes/tts/`: Kokoro-82M, one real VOA sentence at
  0.8x/1.0x/1.15x and a 6-turn VOA dialogue (`af_heart`, `am_michael`); wavs in
  `~/sonari-data/derived/tts/`. RTF on this i5-11400H (WSL2): 0.35-0.41 at 4 threads,
  0.70-0.77 at 1 thread. See `spikes/tts/RESULTS.md`.

## Notes for G1 (P24/P25)
- Whole-clip alignment lets an absent phoneme drift into context: bad.wav scored as
  /θ ʊ k/ put θ inside "and" (competitor æ, not t). Constrain alignment (full context
  sequence or word span) before trusting competitor names. See RESULTS.md.
- `spikes/gop/align.py` is a copy of `tools/evaldata/ctc_align.py`; merge when the
  aligner moves into services/speech.

## Next (pick one per session)
Session prompts: `docs/prompts/BUILD-PROMPTS.md`.
1. P03: ARPAbet → espeak IPA mapping.
2. Design A6 → P12 contracts.
3. P11 Compose (ADR-0001 now in the repo).

## Blockers
- P05: the owner fills in `spikes/tts/CHECKLIST.md` by ear; no quality verdict exists yet.
- This branch is stacked on the P01 branch: merge the P01 PR first, then rebase.
- None for P11.
