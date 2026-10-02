# sonari

Duolingo-style, topic-based English course for Vietnamese students, building IELTS
listening and speaking. Each speaking turn is scored on phoneme-level pronunciation
(wav2vec2 + CTC forced alignment + GOP), fluency, and use of the unit's target
vocabulary and grammar.

Status: pre-M0. See `docs/PLAN-v7.md` for the plan and `docs/adr/` for decisions.

## Local infrastructure

MongoDB (single-node replica set `rs0`, so transactions work) and Redis, in Docker:

```bash
make infra         # create .env from .env.example if missing, start both, wait until healthy
make test-core     # includes the MongoDB integration tests; they skip when it is not running
make infra-reset   # stop and delete this project's volumes (other Docker projects are untouched)
```

`make dev` starts the same infra, then the apps. Both ports are bound to 127.0.0.1. The
init script (`infra/mongo/mongo-init.js`) runs once on an empty volume: after changing it,
run `make infra-reset`.

`make check-imports` fails on any import between bounded contexts (ADR-0001). It is part of
`make lint-core`, so CI runs it.

Sonari is not affiliated with IELTS, British Council, IDP or Cambridge.
English source texts come from VOA Learning English (public domain, VOA-staff items
only) and Tatoeba (CC-BY).
