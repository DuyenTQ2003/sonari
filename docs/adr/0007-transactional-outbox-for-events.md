# ADR-0007: Events leave a context through a transactional outbox

- Status: Accepted
- Date: 2026-10-02

## Context

ADR-0001 rule 2 says contexts talk by events over Redis Streams, published through a
transactional outbox. It does not say why the outbox is needed, or what delivery
guarantee consumers may assume. P14 published `UserRegistered` straight to Redis after
the user was inserted. That has two windows in which state and events disagree:

- **Commit, then crash before the publish.** The user exists and the event is lost.
  Every read model built from `UserRegistered` (learning profile, gamification wallet,
  analytics funnel) never hears of that user, and nothing retries.
- **Publish fails** (Redis down, timeout). P14 logged and moved on, which is the same
  loss. Making the request fail instead would leave an account the learner cannot see
  confirmed, and still no event.

Publishing *before* the commit is worse: a rolled-back registration would announce a
user who does not exist.

MongoDB and Redis cannot share a transaction, so no ordering of two separate writes
closes the window. Only one write can be atomic, and it has to be in MongoDB.

## Decision

1. A context writes its state change and an **outbox document** (event id, type,
   payload, `created_at`, `sent_at: null`) to its own database **in one MongoDB
   transaction** (replica set `rs0`, ADR-0001 rule 4). `MongoOutbox.add` refuses to
   write outside a transaction.
2. A **relay** per context polls unsent entries oldest first, publishes each to the
   stream `events.<Type>`, then marks them sent. It runs as a background task in the
   process that hosts the context. Sent entries expire after 7 days (TTL index).
3. Delivery is therefore **at least once**. A crash between publish and mark-sent, or
   two replicas relaying the same entry, publishes an event twice with the same
   `event_id`.
4. Consumers make that **exactly once in effect**. The `EventConsumer` base class reads
   through a consumer group, acknowledges only after the handler succeeds, records each
   processed `event_id` per group (Redis key with a 7-day TTL) and skips repeats.
5. A failing entry is redelivered after `retry_after_ms`. After `max_deliveries` it moves
   to `dead.events.<Type>` and is acknowledged, so one poison message cannot hold the
   group.

## Consequences

- An event reaches Redis up to one relay interval (default 0.5 s) after the commit.
  Read models are already eventually consistent (ADR-0001), so this changes nothing a
  learner can see.
- Every handler must tolerate redelivery. The processed-id set covers relay duplicates
  and retries after a failure; a crash after the handler's effect and before the id is
  recorded still reapplies it, so database effects should be upserts.
- Writes that emit events need a transaction, which costs a session per request and
  rules out a standalone mongod in any environment.
- Dead-lettered entries need a human. Nothing replays them automatically yet.
- Ordering holds per context outbox and per stream, not across event types.

## Alternatives rejected

- **Publish after commit (P14).** Loses events on a crash, as above.
- **MongoDB change streams instead of an outbox.** No extra collection, but the resume
  token must be stored somewhere durable, the stream carries storage-level documents
  rather than contract-shaped events, and every consumer would couple to another
  context's schema, which ADR-0001 rule 1 forbids.
- **Exactly-once delivery in the transport.** Redis Streams do not offer it, and neither
  does anything else at this budget. Idempotent consumers are the standard answer.
