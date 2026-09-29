# ADR-0001: Modular monolith, processes split by resource profile

- Status: Accepted
- Date: 2026-09-04 (original), rewritten 2026-09-29 — the original file was lost before
  the repository existed; this restates the decision and its reasoning from the project
  notes. Content is authoritative; wording is not the original.

## Context

Sonari is built and operated by one developer on a budget under $10/month. The system
has parts with very different resource profiles:

- HTTP request handling: small memory, latency-sensitive, mostly IO-bound.
- Pronunciation scoring: ~800 MB of model weights resident, CPU-bound, and the single
  most expensive thing per request.
- LLM calls: IO-bound, slow, failure-prone, and driven by prompts that change often.
- Batch jobs: content pipeline, TTS generation, long-running, bursty.

A microservice per domain would mean seven deployments, seven CI pipelines and
cross-service calls for one developer to maintain. A single process would mean model
weights sit in the same memory space as request handling, a batch job can starve
realtime scoring, and a crash in any part takes everything down.

## Decision

A **modular monolith** with **processes split by resource profile, not by domain**.

Seven bounded contexts, each with its own MongoDB database, even when several run in
the same process:

| Context | Owns |
|---|---|
| `identity` | accounts, sessions, refresh-token families |
| `content` | Level, Unit, Lesson, Exercise, Learnable, Source |
| `learning` | progress, unlocks, FSRS cards and review log |
| `gamification` | XP, streak, daily goal |
| `speech` | scoring attempts, calibration data, threshold versions |
| `tutor` | prompts, LLM call logs, cost ledger |
| `analytics` | raw events and funnel read models |

Process layout:

- Launch with **two** processes: `core` (identity + content + learning + gamification)
  and `speech`.
- Reach **four** at full build-out: `core`, `speech`, `ai-gateway` (tutor),
  `worker` (batch).
- `analytics` stays inside `core` until event volume justifies moving it.

Rules that keep the contexts real rather than decorative:

1. **Never join or query across contexts.** No `$lookup` across databases, no direct
   import of another context's models.
2. Contexts communicate by **events over Redis Streams**, published through a
   transactional outbox.
3. A context that needs another's data keeps a **local read model**, updated from those
   events, and accepts that it is eventually consistent.
4. MongoDB runs with `--replSet rs0` so the outbox write and the state change share one
   transaction. Dev connection strings use `directConnection=true`.
5. An automated import check fails the build on a cross-context import.

## Why split by resource profile

- **`speech` is separate** because it holds ~800 MB of weights. Co-locating it means
  every `core` deploy reloads them, and an OOM in either kills both. It must survive
  alone, and it must be able to shed load (503) without taking the app down.
- **`ai-gateway` is separate** because prompts change constantly and providers fail.
  It needs its own deploy cadence, its own timeouts and its own failover, none of which
  should force a `core` restart.
- **`worker` is separate** because batch jobs must never block realtime requests. A
  content generation run or a TTS batch competing for the same event loop as a scoring
  request is a latency bug waiting to happen.

## Consequences

- Splitting later is cheap: a context already owns its database and talks in events, so
  moving it to another process is a deployment change, not a rewrite.
- Eventual consistency is now a product concern. A learner may briefly see stale XP.
  This is accepted; the alternative is cross-context joins.
- Every cross-context read costs a local read model to build and keep correct. That is
  the price of the rule, and it is paid deliberately.
- Two processes at launch is more operational surface than one. It is the minimum that
  protects the memory-heavy part.
