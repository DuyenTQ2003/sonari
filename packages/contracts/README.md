# packages/contracts

JSON Schemas shared by the frontend and backend (`ScoreResponse`, events). Contract
changes happen here first, then in FE and BE. Schemas go in `schema/`.

`schema/events/user-registered.schema.json` was added by P14 ahead of P12, because auth
publishes it. Nothing else is here until the A6 design is done, and there is no codegen yet:
P12 adds it and should replace the hand-written model in `sonari_core/identity/events.py`.
