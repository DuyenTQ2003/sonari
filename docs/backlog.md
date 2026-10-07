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
- Decide whether the parser should read bullet lists in the body. `<li>` text inside `div.wsw` holds 530
  lines (23,763 words) on 309 pages; 124 lines are the same comment-box instructions, the rest are real
  bullet points. The bare-text fix skips lists as instructed (`docs/reports/voa-corpus.md`).
- `has_audio` may be wrong on some old pages: 962 pages (380 passages) have an `.mp3` link in some letter case
  but `has_audio` is false. `parse.MP3` is case-sensitive (`.Mp3` in 2010-2012 pages) and `parse_page` only
  looks inside `#article-content`. Not analysed further; check before relying on `has_audio`.
- Pair the audio-only pages with their text page: 7,700 text-less pages share a title with a passage
  (more by fuzzier matching), so a passage could get its listening audio from the twin page.
- ADR-0008 recall (not planned: the 90% target was withdrawn, `docs/reports/voa-trim-corpus.md`; kept as a
  record of what is left). 57% of the 5% set is free of missed frame. By lines in the round-two sample, with the
  passages that hold one: A closings and
  teasers in plain prose, "Join us again soon for Part 2", "We leave you with ... singing" (22 lines, 19
  passages); B programme blurbs and openers with other wording, "Each week we explore ..." (12, 12); C practice
  or discussion prompts without a channel word, "Practice what you learned today!" (9, 8); D editor or series
  notes, cross-references, page headers (7, 6); E pointers to a video, a song or a page (8, 5). Covering A, B
  and C would give about 89% in the sample (in-sample). A and B read like content in a lesson body, so each
  needs closed anchors (a series name) and the reading of ADR-0008 section 5, and a rule that needs the
  position of the line in the passage is a new idea that the ADR has not weighed.
- Closed versions of rules that had an open slot, if recall is ever wanted back (each needs the evidence of
  ADR-0008 section 5): credits with an explicit list of nouns after "wrote this" (lesson, story, report, ...),
  VITA leaflets by topic, the opener with the programme titles listed, glossary entries as exact sentences. The
  open versions removed 4,568 lines (`docs/reports/voa-trim-corpus.md`).
- A blocking screen for what recall cannot reach: block a passage that has a line with a channel, a programme
  word or a closing phrase left after the rules. About 83-87% clean on the "before" sample (in-sample), at the
  cost of more than a third of the passages. Not adopted; only if cleanliness matters more than the count.
- `make voa-precision`: the sampler and summariser behind `voa-trim-precision.md`, `voa-trim-recall.md` and
  `voa-trim-corpus.md` were one-off scripts (seeds 20261003 to 20261008; populations and strata are in the
  reports). Make them a target
  that draws the samples, writes the TSV to label and prints the counts with exact intervals, so every change
  to the lists can be re-measured. The grade is computed with the lines the rules miss still in, so recompute
  it as recall improves (below grade 7 was 3,253, 3,335, 3,214 and 3,313 passages with the four rule sets).
- Not stored on `Source` (ADR-0010 ingests the trimmed corpus as it is): the "Words in This Story" glossary,
  which the parser splits off, and the credit lines the parser drops before the trim; both are in the cached
  HTML. P50 decides whether they matter.
- `Source` stores no word count of `text`. The service counts it to check the window
  (`trim_rules.count_words`), so a reader that needs the length (P50's filters) can call that. Store a number
  only if a query has to filter on it, which would be a contract change, tools first.
- `SourceIngested` event for the other contexts (ADR-0001: they keep read models, they never query `content`).
  Nothing consumes Sources yet, so none exists; add it with its first consumer.
- `--dry-run` counts a rollback (a stored older version made current again) as `superseded`, like a
  re-trim, because the real run's summary does. To tell them apart, split the outcome in `_decide`
  (`content/ingest.py`), which the run and the plan both ask.
- Provenance of the batch is not on `Source`: only `ingested_at`. The manifest's `snapshot.index_sha256` (which
  crawl) and `trimmed_jsonl_sha256` (which file) are checked at ingest and then dropped. Add them if an audit
  ever needs to name the crawl a stored trim came from.
- The cap's two sides are counted differently. `removed_words` counts by whitespace and leaves page furniture
  out; `original_words` is the corpus tokeniser over every line of `original_text`, furniture included (all 724
  stored records; ADR-0010 called it "editorial words"). The gap is small and runs both ways. Both are enforced
  as the writer produces them (`trim_rules.py`); whether they should share one tokeniser is a superseding ADR.
- `TrimmedPassage` is also what `Source` is read through, so a rule in `trim_rules.py` that tightens later makes
  older stored versions fail to load, and ADR-0010 keeps them. Decide before such a change lands whether stored
  versions are migrated or only a file entering is validated.
- `make test-scripts` pins pydantic, beanie and what they pull in to the core lock (`scripts/locked_pins.py`);
  pytest, pyyaml and uv itself still float.
- One passage ends a content line with the page furniture "Return to main page" glued on (a letter in the
  *Dear Doctor* series); a whole-line trim cannot cut it. Parser territory, not touched here.
- Classification (`docs/reports/voa-classify.md`), ideas only, none coded. The stems are narrowed
  (`docs/reports/voa-safety-stems.md`); what stems cannot fix is how a mention is counted: count a stem once per
  paragraph (one anecdote gave "politician" 4 times and 5 war words; "President Donald Trump" counts as `president`
  and `trump`), and read a sample of passages the flags left alone, which no pass has done.
- The "American Mosaic:" title makes a magazine even when the stored text is one segment (1 of 3 read); look at the
  text. An English lesson with no programme and no lesson title ("Some New Words for VOA's Word Book") is tagged
  explainer. The 50 labels have one labeller (the assistant): have the owner overrule any, and read a second sample
  that was not used to write the rules.
- The unit tags (`units.tsv`) are not validated: 352 of the 724 match no unit, and 7 of 15 reader letters are
  tagged *Study and work*. Measure their precision on a read sample before the per-unit counts decide a unit.
- Missed frame by type: voa-trim-corpus.md measured 57% of the 724 as free of a frame line the lists miss, mostly in
  the lesson programmes. Re-measure it on the 370 explainers and news items, the set the reading path draws from.
- `--dry-run` for `ingest_speaking_items.py`, as `ingest_sources.py` has: bind without indexes and
  report. Left out of the speaking-items PR to stay under its 250-line budget.
