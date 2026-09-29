# HANDOFF

Last updated: 2026-09-29

## Done
- `CLAUDE.md`, `docs/PLAN-v7.md`, `docs/adr/0006-source-first-authoring.md`
- `docs/design-system.md` updated to v7 (course structure, screen inventory, new prompts
  for B14, B14b, B20, B24)
- P10 monorepo skeleton: `services/core` and `services/speech` (uv, Python 3.11, src
  layout, ruff, strict mypy, pytest, `/healthz` + one test each), `apps/web` and
  `packages/contracts` placeholders, root `Makefile`, `.pre-commit-config.yaml`,
  `.github/workflows/ci.yml`, `scripts/check_no_vietnamese.py` (+ tests).

## Working mode
FE and BE are built in parallel against a **mock speech-service** that returns a frozen
`ScoreResponse`. The AI spike runs alongside, not after. Rationale: if GOP fails, the
contract survives and the FE/BE work is not wasted.

## Next (pick one per session)
Session prompts: `docs/prompts/BUILD-PROMPTS.md`. Start with P01 (AI) and P10 (BE).

1. Copy existing ADR-0001 and ADR-0004 into `docs/adr/` (not recreated here).
2. Design A6 in a design tool → write `packages/contracts/score-response.schema.json`.
3. M0 spike: wav2vec2 on `good.wav` vs `bad.wav`. **Report the numbers.**
4. M1: Compose (Mongo rs0 + Redis) — task P11.
5. M0: VOA inventory — usable VOA-staff items with audio per level and topic.

## Blockers
- `make` and `pre-commit` are not installed on the dev machine, and the folder is not a
  git repo yet. P10 checks were run by invoking the Makefile recipes directly and
  pre-commit via `uvx` in a throwaway git copy. CI has not run yet: `git init`, push, and
  confirm the first run is green.
- None otherwise. Item 3 can invalidate the plan; do it before any large FE/BE investment.
