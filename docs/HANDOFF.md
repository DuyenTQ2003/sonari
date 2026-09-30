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
- **P03 done.** `spikes/gop/phoneset/`: `arpabet_to_espeak.yaml` (39 phones plus context
  rules), `mapping.py`, `check_vocab.py` (50/50 tokens in vocab), `roundtrip_test.py`,
  `REPORT.md`. 200 NGSL words vs espeak-ng: 88.0% strict, 93.0% after fold rules; the 14
  left are all accent variants. The 8 hand-written spike tokens agree with the table.
  Run `make check-phoneset` (needs network + espeak-ng; not in CI). Moves to
  `services/speech` at P21.

## Notes for G1 (P24/P25)
- Whole-clip alignment lets an absent phoneme drift into context: bad.wav scored as
  /θ ʊ k/ put θ inside "and" (competitor æ, not t). Constrain alignment (full context
  sequence or word span) before trusting competitor names. See RESULTS.md.
- `spikes/gop/align.py` is a copy of `tools/evaldata/ctc_align.py`; merge when the
  aligner moves into services/speech.
- One reference token per phone will give false errors on correct speech for unstressed
  vowels (`ə ɐ ᵻ ɪ`), the US flap (`t d ɾ`) and syllabic `əl` (espeak emits one token).
  Untested against model output; see REPORT.md, last section, before P22/P25.

## Next (one per session; prompts in `docs/prompts/BUILD-PROMPTS.md`)
1. P04: ONNX export + CPU benchmark.
2. Design A6 → P12 contracts.
3. P11 Compose (ADR-0001 now in the repo).

## Blockers
- None.
