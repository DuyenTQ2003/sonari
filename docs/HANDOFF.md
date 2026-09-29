# HANDOFF

Last updated: 2026-09-29

## Done
- Docs: PLAN-v7, CLAUDE.md, ADR-0006, design-system (v7), BUILD-PROMPTS, eval-data
- P10 scaffold: core + speech services, Makefile, pre-commit, CI. Repo pushed, CI green.

## Open bug
- `make typecheck` prints "Nothing to be done" — mypy never runs, so the target passes
  vacuously. Fix before trusting CI. A guard test must assert every target named in
  ci.yml exists in the Makefile.

## Plan change (2026-09-29)
No audio is recorded for this project. The single Pearson r gate is replaced by
G0/G1/G2/G3 (PLAN-v7 §9.1), all built from public datasets:
- G0: two LibriSpeech clips, selected by script (blocking, M0)
- G1: 200 LibriSpeech minimal-pair items, errors made by substituting the reference
  text, not the audio (blocking, M2)
- G2: Common Voice non-native slice, or L2-ARCTIC if access is granted (reported)
- G3: Pearson r on real consented learner audio — backlog, needs launch
See `docs/eval-data.md`. The native-speech / Vietnamese-learner gap is stated in the
README, not hidden.

## Working mode
FE and BE build in parallel against the mock speech-service (P17). The AI spike runs
alongside, not after.

## Next (pick one per session)
Session prompts: `docs/prompts/BUILD-PROMPTS.md`.
1. Fix the typecheck target + guard test.
2. Copy ADR-0001 and ADR-0004 into docs/adr/.
3. P01 (fetches LibriSpeech, builds the G0 pair, runs the spike) → P02 (gate G0).
4. Design A6 → P12 contracts.
5. P11 Compose (needs ADR-0001 for the 7 context names).

## Blockers
- P02 (G0) can invalidate the plan. Do it before large FE/BE investment.
- P11 is blocked until ADR-0001 is in the repo.
