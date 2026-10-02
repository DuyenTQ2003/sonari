
# CLAUDE.md

Read this file, then `docs/HANDOFF.md`, at the start of every session. Read
`docs/PLAN-v7.md` and `docs/adr/` only when the task touches them.

## Project


Sonari: a Duolingo-style, topic-based English course for Vietnamese students that
builds IELTS listening and speaking. There are 7 difficulty levels, and the MVP is
level 4 (reference band 4.5–5.0). Each speaking turn is scored on pronunciation (GOP,
per phoneme), fluency, and task completion.

## Language rule

- Talk to the developer in Vietnamese.
- Everything else is English: code, comments, docstrings, identifiers, commit messages,
  markdown, ADRs, prompts, test names, log messages, API field names.
- Learner-facing copy is Vietnamese and lives only in `apps/web/messages/vi.json`.
  Never inline Vietnamese strings in components.

## Repo layout (target)

```
apps/web/              Next.js 15 App Router, TypeScript, Tailwind, shadcn/ui
services/core/         FastAPI: identity + content + learning + gamification
services/speech/       FastAPI: G2P, wav2vec2 ONNX, alignment, GOP, fluency, task match
services/ai-gateway/   FastAPI: LLM calls, prompts, failover        (later)
services/worker/       arq: content pipeline, TTS batch             (later)
packages/contracts/    JSON Schemas shared by FE and BE (ScoreResponse, events)
docs/                  PLAN, ADRs, design system, HANDOFF, backlog
```

## Architecture rules (ADR-0001)

- Processes are split by resource profile, not by domain. Launch with `core` + `speech`.
- There are 7 bounded contexts and 7 MongoDB databases, even when they share a process.
- **Never join or query across contexts.** Consume events (Redis Streams) and keep
  local read models.
- MongoDB runs with `--replSet rs0`. Dev connection strings use `directConnection=true`.

## AI rules

- **Never use Whisper (or any STT) for pronunciation scoring.** Its language model
  corrects the speaker. STT is for transcripts only.
- GOP pipeline: `g2p_en` → ARPAbet→espeak IPA map → wav2vec2-lv-60-espeak (ONNX, CPU)
  → CTC forced alignment → GOP → versioned thresholds.
- Phoneme feedback in Vietnamese comes from a lookup table, not an LLM.
- Production LLM use goes through APIs, never a self-hosted GPU (ADR-0004). Budget is
  < $10/month total.
- There are no LLM calls at learner runtime in the MVP. Content is pre-generated
  offline.

## Data rules (ADR-0006)

- **No generated English source text, at any level.** English comes from VOA (only
  items credited to VOA staff; no AP/Reuters or third-party media) or Tatoeba (CC-BY,
  attribution shown).
- The LLM generates scaffolding only: questions, distractors, Vietnamese glosses,
  grammar explanations.
- Never copy real exam content (Cambridge, British Council, IDP, ETS).

## Code conventions

- Python 3.11, type hints everywhere, Pydantic v2 models at every API boundary.
- Keep files under 300 lines. Split before exceeding.
- Every scoring component ships with a test. `make test-speech` must stay under 10 s.
- OpenTelemetry spans from day one. LLM spans use `gen_ai.*` attributes.
- Contract changes happen in `packages/contracts/` first, then in FE and BE.

## Session protocol

1. Pick one task from `docs/HANDOFF.md` that fits one session.
2. Finish at a committable state: tests pass, no half-done refactors.
3. Update `docs/HANDOFF.md`: done, next, blockers. Keep it under 40 lines.
4. New ideas go to `docs/backlog.md`. Do not code them.
5. Never re-litigate an ADR. If one looks wrong, say so and propose a superseding ADR.

## Priority when budget runs short

eval → observability → agent → optimization. Cut from the end.
Never cut: the basic eval harness, GOP calibration.

## graphify

This project can use a knowledge graph at graphify-out/. It is not generated yet;
run `graphify .` to create it. Until then, skip the rules below.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Git workflow

- `main` is protected: never commit or push to it directly. Pushes are rejected
  server-side and every PR needs 3 green CI checks.
- **Branch first, work second.** Every session starts with:
  `git checkout main && git pull && git checkout -b <prefix>/<slug>`
  Prefixes: `feat/`, `fix/`, `chore/`, `docs/`, `test/`.
- Squash merge only; the branch is deleted on merge.
- A PR body states what changed and the command that proves it.
- Work only in `~/sonari` (WSL). Never open or edit the repo from a Windows path.
- Stacked PR whose base was squash-merged: `git rebase --onto origin/main <old-base-tip>`.
  Never merge main into it, and never use GitHub's web conflict editor on code files.
- No AI attribution in commit messages or PR bodies.

### Session automation

Claude runs the whole loop except the merge:

1. `git checkout main && git pull && git checkout -b <prefix>/<slug>`
2. implement the task
3. `make lint typecheck test` — fix until green
4. `git add -A && git commit` with a conventional message
5. `git push -u origin <branch>`
6. `gh pr create --fill`
7. `sleep 15 && gh pr checks --watch`
8. report the PR number and stop

The human reviews the diff and merges. Never run `gh pr merge`, never use
`--admin`, never push to `main`.
