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
- Event bus follow-ups (P15): a CLI to inspect and replay `dead.events.*` entries, and
  W3C `traceparent` carried in the stream entry so a consumer span joins the producer's
  trace. Raised by ADR-0007.
- G2P follow-ups (P21): homograph disambiguation ("read", "live"; the backend takes CMUdict's
  first variant, g2p_en would use POS tags); generate `g2p/lexicon.yaml` entries for each
  unit's vocabulary by comparing CMUdict variants with espeak-ng (a probe on 2026-10-03 found
  camera, restaurant, average, every, different); download `cmudict` in CI so the 35 live g2p
  tests run there.
- Hooks skipped in merge commits (found while fixing `check-merge-conflict`, measured 2026-10-03
  in a throwaway repo; none fixed yet): (1) a merge that git commits by itself (no conflicts) runs
  only the commit-msg hook, because `make setup` installs `pre-commit` and `commit-msg` but not
  `pre-merge-commit`, so a file with trailing whitespace or unused imports comes in unchecked; (2) a merge
  with conflicts runs the pre-commit hooks on the conflicted files only (pre-commit's own rule, "Checking
  merge-conflict files only"), so a Python file that merged cleanly is not linted. CI's
  `pre-commit run --all-files` still checks everything on the PR. Option: `pre-commit install --hook-type
  pre-merge-commit` in `make setup`, with `stages: [pre-commit, pre-merge-commit]` on the hooks.
- Speech runtime follow-ups (P20): a smaller image (the ffmpeg package is 464 MB of 1.1 GB; a
  static ffmpeg build would be about 70 MB); the OpenTelemetry SDK, exporter and FastAPI
  instrumentation for the speech service as core has them (the runtime already creates
  `speech.decode` and `speech.infer` spans through the API), with the first HTTP endpoint
  (P23); real iPhone and Chrome recordings as fixtures instead of the synthetic ones; capacity
  numbers measured on the VPS.
- CI follow-ups (#28): the 4 tests on the real int8 model still skip in CI: `runtime/models.yaml` has
  a URL now, but CI deliberately does not download 355 MB. To run them, fetch it in the speech job with
  `actions/cache` keyed on the pinned SHA-256 (the first run downloads it, later runs restore it).
  If the core job grows (it is 42 s now, 24 s of it starting MongoDB and Redis), cache the mongo and redis
  images, or run only `mongod` for the tests that do not need Redis.
- check-merge-conflict does not fire on commits created during a rebase; markers
  were pushed twice today (#26, #28) through that gap. Add a CI step that greps
  for markers in tracked text files. CI is the surer place: it covers every path
  into main, regardless of which git command created the commit.
- `make setup` does not install the pre-merge-commit hook, so a clean merge that
  git commits itself runs only commit-msg hooks. Add
  `pre-commit install --hook-type pre-merge-commit` to `make setup`.
- Add a CI check that fails when any models.yaml entry has a null or empty url.
  PR #26 merged with `url: null`; draft status is a convention, not an
  enforcement.
- Cap PR size going forward. #26 was 38 files / 2392 lines in one commit, past
  the point where review is real. Split prompts by layer, target under 500 lines.
- A Cloudflare R2 mirror of the int8 model, as the second entry of `url` in `runtime/models.yaml` (a
  commented TODO there), so that a Hugging Face outage cannot stop an image build. The fetcher already
  tries the list in order; the CI check rejects a placeholder that is left in.
- Make `voa_inventory.parse` read bare text in `#article-content` (`div.wsw`, `div.wordclick`, split on
  `<br />`). 942 pages with 1-99 words are articles it misses, plus 40 passages it reads in part; the
  fix and its test plan are in `docs/reports/voa-missing-pages.md`. Then rerun `make voa-corpus`.
- Pair the audio-only pages with their text page: 7,700 text-less pages share a title with a passage
  (more by fuzzier matching), so a passage could get its listening audio from the twin page.
