# HANDOFF

Last updated: 2026-09-30

## Done
- Docs: PLAN-v7, CLAUDE.md, ADR-0001/0004/0006, design-system (v7), BUILD-PROMPTS,
  eval-data. P10 scaffold (core + speech, Makefile, pre-commit, CI).
- Typecheck target fixed + CI/Makefile guard test (#1). ADR-0001 and ADR-0004 restored (#4).
- **P01 done, both clips PASS.** `tools/evaldata/` fetches LibriSpeech dev-clean and
  builds the G0 pair by script ("think" vs "took", same speaker). wav2vec2-lv-60-espeak
  decodes θ and t as expected. See `spikes/gop/RESULTS.md`.
- **P02 done, GATE G0 PASS.** Numpy CTC Viterbi (`spikes/gop/align.py`) + naive GOP
  (`run_gop.py`): θ|correct gop +3.89, t|substituted gop −5.71, competitor θ.
- Root `pyproject.toml` (`sonari-tools`, not a workspace) so `uv run python tools/...`
  works from the repo root. New `make test-tools` (numpy-only) runs in CI.
- **P06 built, inventory partial (0.9%).** `tools/voa_inventory/`: polite resumable crawler,
  parser, licence filter, level/topic tags, report. 600 of 67,337 sitemap URLs sampled at
  random: 73 usable; 96 of 169 audio+text pages fail the licence filter. 7 of 8 level 4
  topics have < 2 usable items in this sample (not conclusive). `docs/voa-inventory.md`.

## Notes for G1 (P24/P25)
- Whole-clip alignment lets an absent phoneme drift into context: bad.wav scored as
  /θ ʊ k/ put θ inside "and" (competitor æ, not t). Constrain alignment (full context
  sequence or word span) before trusting competitor names. See RESULTS.md.
- `spikes/gop/align.py` is a copy of `tools/evaldata/ctc_align.py`; merge when the
  aligner moves into services/speech.

## Next (one per session; prompts in `docs/prompts/BUILD-PROMPTS.md`)
1. P03: ARPAbet → espeak IPA mapping.
2. Design A6 → P12 contracts.
3. P11 Compose (ADR-0001 now in the repo).

## Blockers
- P06: finish the crawl in your own terminal (about 18 h, resumable), then `make voa-report`:
  `VOA_CONTACT_EMAIL=you@x.com make voa-crawl ARGS="--limit 100000"` (Claude background jobs
  stop after 10 minutes).
- This branch is stacked on the P01 branch: merge the P01 PR first, then rebase.
- None for P11.
