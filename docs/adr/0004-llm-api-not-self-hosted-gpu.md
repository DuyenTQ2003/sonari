# ADR-0004: Production uses LLM APIs, not a self-hosted GPU

- Status: Accepted
- Date: 2026-09-04 (original), rewritten 2026-09-29 — the original file was lost before
  the repository existed; this restates the decision and its reasoning from the project
  notes. Figures are the ones recorded at the time and are not re-derived here.

## Context

The project needs an LLM for offline content scaffolding (distractors, Vietnamese
glosses, grammar explanations, speaking questions) and, later, for a tutor agent.
Self-hosting an open model on a rented GPU is the reflexive choice for an AI portfolio
project: it looks more impressive and removes per-token cost.

The decision is an arithmetic one, not an aesthetic one.

## Decision

Production uses **hosted LLM APIs**. Local models are for development and as a
fallback path only.

Recorded figures:

- Dedicated GPU pod: **~$197/month**, paid whether or not it is used.
- API usage at this project's volume: **$2–8/month**.
- The break-even point sits roughly **1500x above** expected volume.
- Total operating budget: **under $10/month**.

Cost levers that are used instead of self-hosting:
- Cached input at roughly 10% of the normal price.
- Batch mode at roughly 50% off, for every offline generation job.
- One-off content generation for 5000 items costs $1.50–47 depending on model.

## Why a GPU is worse here, beyond price

- A GPU pod is a **fixed** cost against **bursty** demand. Content generation runs for
  hours a few times per level, then nothing for weeks. Utilisation would be near zero.
- Self-hosting means owning model serving, quantisation, batching and OOM debugging.
  None of that is the thing being built, and all of it consumes the scarce resource:
  developer sessions.
- Model quality moves faster than the cost saving. An API lets the model change with a
  config edit.

## Consequences

- There is a hard dependency on external providers. Mitigated in `ai-gateway`: a
  primary and a fallback provider, timeouts, retry with jitter, and a hard daily spend
  cap.
- Prompt and output data leave the system. No learner audio and no personal data is
  ever sent to an LLM; only text being generated for content.
- There are **no LLM calls at learner runtime in the MVP**. Everything a learner touches
  is deterministic or pre-generated, so provider latency and outages cannot affect a
  lesson.
- Local models stay in the loop for development, so the fallback path is exercised
  rather than theoretical.

## What would reverse this

Sustained volume at roughly 1500x current levels, or a compliance requirement that
content generation not leave owned infrastructure. Either would justify a superseding
ADR, not an amendment to this one.
