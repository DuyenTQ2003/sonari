# packages/contracts

JSON Schemas shared by the frontend and backend (`ScoreResponse`, events). Contract
changes happen here first, then in FE and BE. Schemas go in `schema/`.

`schema/events/user-registered.schema.json` was added by P14 ahead of P12, because auth
publishes it. Nothing else is here until the A6 design is done, and there is no codegen yet:
P12 adds it and should replace the hand-written model in `sonari_core/identity/events.py`.

## Event envelope on Redis Streams (ADR-0007)

Each event type has its own stream, `events.<Type>` (for example `events.UserRegistered`).
An entry has two fields:

- `event_id`: the payload's `eventId`, repeated so consumers can deduplicate before parsing.
- `data`: the payload as JSON, valid against `schema/events/<type>.schema.json`.

Delivery is at least once. A consumer group that gives up on an entry copies it to
`dead.events.<Type>` with `source_entry_id`, `group` and `deliveries` added.
