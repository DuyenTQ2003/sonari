# From a fresh clone: what was run, how long it took, what was not run

Date: 2026-10-08. Branch `docs/readme-fresh-clone` at `dcb8ce0`. Machine: 12-core laptop, WSL2,
Ubuntu 26.04, home network. Script: one bash script in a scratch directory, every step timed.

**Empty at the start:** the clone directory, `DATA_DIR`, the uv package cache, uv's Python
installs and the npm cache, so every download really happened. **Already installed:** git 2.53,
GNU make 4.4.1, uv 0.12.22, Node 22.22.1 with npm 9.2.0, ffmpeg 8.0.1,
espeak-ng 1.52.0.

## What ran

| # | Step | Time | Network | Result |
|---|---|---|---|---|
| 1 | `git clone` (GitHub) | 2 s | yes | ok |
| 2 | `make setup` (git hooks; `uvx` fetches pre-commit) | 3 s | yes | ok |
| 3 | `make speech-data`: Python 3.11.17 (29.4 MiB), the speech service's packages, the int8 model (355,352,992 bytes from Hugging Face, size and SHA-256 checked against `runtime/models.yaml`), CMUdict (NLTK) | 56 s | yes | ok |
| 4 | `uv run --directory services/speech python -m sonari_speech.runtime.weights --check` | 0 s | no | ok |
| 5 | core's packages (`uv run --directory services/core ...`) | 3 s | yes | ok |
| 6 | `make apps/web/node_modules` (`npm ci`) | 12 s | yes | ok |
| 7 | `make build-web` (not needed to score; checks the web app builds) | 27 s | no | ok |
| 8 | speech service started on port 8301, ready (`/readyz` 200) | 5 s | no | ok |
| 9 | `POST /v1/score`, LibriSpeech G0 `good.wav`, "One think you." | 0.33 s | no | 200, thresholds `v2-native-s20261008-val20261009`, 3 of 3 words correct |

**Clone to a scored sentence: 108 s**, 27 s of it the web build that scoring does not need. Downloaded:
344 MB into `DATA_DIR`, 288 MB of Python packages, 95 MB of Python, 168 MB of npm packages.
Docker images (`mongo:7.0`, `redis:7-alpine`) were not pulled, so they are not in these numbers.

## What was not run, and why

`make infra`, `make ingest-demo-sources`, `make ingest-speaking-items` and `make dev`, so **the
practice page was not reached from this clone**. Two reasons, either one enough:

1. **Docker does not run here.** In this WSL distro `docker` fails with
   `/usr/bin/docker: Input/output error`, so `docker compose up` cannot start.
2. **The Makefile cannot run a second stack beside the owner's.** `COMPOSE_PROJECT_NAME` does
   override the project name `sonari` (compose gives it precedence), but the host ports are fixed:
   27017 and 6379 in `compose.yaml` (and in the URIs of `.env.example`), 8000, 8001 and 3000 in
   `make dev`. The owner's stack holds those ports, and the brief says to report this rather than
   work around it. Making them variables is a small change, not made here.

What covers the unrun part instead: `services/core/tests/test_demo_seed.py` runs in CI without a
database and checks that the 13 seed passages pass the same validation `make ingest-sources`
applies and that each of the 20 sentences is where `make ingest-speaking-items` looks for it. The
ingest scripts themselves ran against a live MongoDB in earlier sessions (`docs/HANDOFF.md`).

## What broke, and what changed

- **The practice page needed a 14-hour crawl.** `make ingest-speaking-items` requires the passages
  each sentence pins, and those came only from the full trimmed corpus, which needs the VOA crawl
  (47,854 pages, [voa-corpus.md](voa-corpus.md); the crawl log on the owner's machine shows 0.91 to
  0.98 pages a second, about 14 hours). Fixed: `tools/speaking_items/sources.jsonl` holds those 13
  passages, byte for byte from the trimmed corpus, and `make ingest-demo-sources` ingests them.
  Ingesting the full corpus later leaves them unchanged (same `_id`, same content; ADR-0010).
- **The model and CMUdict had no make target.** `make speech-data` fetches both and checks that
  ffmpeg and espeak-ng are installed. `make demo` chains the whole path.
- Nothing else broke in the steps that ran.
