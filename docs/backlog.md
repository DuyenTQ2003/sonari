# Backlog

Ideas parked here are not planned. Moving one into a milestone needs a reason in the
PR description.

- Levels 1–3 and 5–7
- Placement test (needs a second level)
- Roleplay screen B18 (levels 1–3)
- LLM roleplay partner
- Estimated speaking band (gated by QWK ≥ 0.6 vs human raters)
- Leagues
- Agent tutor, MCP server, grammar RAG
- Reading, writing
- Web push reminders (email first)
- Beginner-friendly TTS for levels 1-3: 0.8x alone is not enough. Options, cheapest
  first: try other Kokoro voices; insert 300-500 ms pauses at clause boundaries;
  play each line twice (slow with pauses, then natural). Raised after the P05 spike.
- Topic labels: a second labeller on the same 100 pages (agreement is unmeasured), and a
  stratified top-up sample for topics with fewer than 10 labelled pages, so per-topic
  precision and recall can be reported for them. Raised by the P06 tagger evaluation.
- Part 1 starter (speaking only, no VOA passage): examiner-style questions on hometown,
  home/accommodation and family, which open most IELTS Part 1 tests but have no level 4
  VOA source. Questions are scaffolding under ADR-0006. Raised by
  `docs/level4-units-proposal.md`.
- CI integration tests: add a MongoDB replica-set service to the `core` job so the P11
  transaction and access tests run in CI; today they skip there because CI has no MongoDB.
- MongoDB users for the later processes: `ai-gateway` (owns `tutor`, no user exists yet)
  and `worker` (ADR-0001 does not say which databases it writes). Add them, with the
  matching `.env.example` entries, when those processes are created. Raised by P11.
