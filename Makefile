SERVICES := core speech
UV_RUN := uv run --directory

LINT_TARGETS := $(SERVICES:%=lint-%)
TYPECHECK_TARGETS := $(SERVICES:%=typecheck-%)

# Every target is phony (none produces a file of that name).
# NOTE: make skips implicit (%) rule search for phony targets, so per-service targets
# must use static pattern rules ("targets: pattern:"), never a bare "lint-%:" rule;
# otherwise they silently become empty recipes ("Nothing to be done").
.PHONY: setup dev infra infra-reset lint typecheck test test-core test-speech test-scripts \
	test-tools check-phoneset check-imports fmt lint-scripts $(LINT_TARGETS) $(TYPECHECK_TARGETS)

# One-time setup per clone: the pre-commit hook and the commit-msg hook (strips AI trailers).
# Git worktrees of the clone share these hooks.
setup:
	uvx pre-commit install
	uvx pre-commit install --hook-type commit-msg

# Local settings. Created once from the example and never overwritten.
.env:
	cp .env.example .env

# MongoDB (single-node replica set rs0) and Redis; returns once both are healthy.
infra: .env
	docker compose up -d --wait

# Stops the stack and deletes its named volumes. Scoped to the compose project "sonari",
# so volumes of other projects are untouched.
infra-reset: .env
	docker compose down --volumes --remove-orphans

# Starts the infra, then the apps in the foreground. Use `make infra` when you only need
# the databases (for example `make infra && make test-core`).
dev: infra
	@trap 'kill 0' INT TERM; \
	$(UV_RUN) services/core --env-file $(CURDIR)/.env uvicorn sonari_core.main:app_factory --factory --reload --port 8000 & \
	$(UV_RUN) services/speech uvicorn sonari_speech.main:app --reload --port 8001 & \
	wait

lint: $(LINT_TARGETS) lint-scripts

$(LINT_TARGETS): lint-%:
	$(UV_RUN) services/$* ruff check .
	$(UV_RUN) services/$* ruff format --check .

# ADR-0001 rule 1: fails on any import between bounded contexts. Part of lint-core, so CI
# runs it.
check-imports:
	$(UV_RUN) services/core lint-imports

lint-core: check-imports

lint-scripts:
	uv run --no-project --with ruff ruff check scripts tools spikes
	uv run --no-project --with ruff ruff format --check scripts tools spikes
	uv run --no-project python scripts/check_no_vietnamese.py services scripts tools spikes

typecheck: $(TYPECHECK_TARGETS)

$(TYPECHECK_TARGETS): typecheck-%:
	$(UV_RUN) services/$* mypy

test: test-core test-speech test-scripts test-tools

test-core:
	$(UV_RUN) services/core pytest

# Must stay under 10 s and must not load model weights.
test-speech:
	$(UV_RUN) services/speech pytest

test-scripts:
	uv run --no-project --with pytest --with pyyaml pytest -q scripts/tests

# numpy-only tests (tools + spike aligner); neither torch project is installed for these.
test-tools:
	uv run --no-project --with pytest --with numpy --with pyyaml pytest tools spikes/gop/tests

# VOA inventory (P06): a polite, resumable crawl into DATA_DIR/voa_cache, then an offline
# report. The crawl needs VOA_CONTACT_EMAIL (it goes into the User-Agent). Not part of CI.
.PHONY: voa-crawl voa-report voa-sample voa-evaluate voa-corpus voa-trim voa-wordlists voa-missing
voa-crawl:
	PYTHONPATH=tools uv run --no-project --with pyyaml python -m voa_inventory.crawl $(ARGS)

voa-report:
	PYTHONPATH=tools uv run --no-project --with pyyaml python -m voa_inventory.report $(ARGS)

# The CEFR word lists of tools/voa_corpus: CEFR-J 1.5 and Octanove C1/C2, pinned to a commit of
# openlanguageprofiles/olp-en-cefrj and checked against tools/voa_corpus/wordlists.sha256. Not
# copied into the repo (the CEFR-J terms say nothing about redistribution).
WORDLIST_DIR ?= $(HOME)/.cache/sonari/wordlists
WORDLIST_URL := https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/d4e45b75b38f27b30dfc5c44d8c571aec7e7092f
voa-wordlists:
	mkdir -p $(WORDLIST_DIR)
	for f in $$(awk '{print $$2}' tools/voa_corpus/wordlists.sha256); do \
	  [ -f $(WORDLIST_DIR)/$$f ] || curl -fsSL -o $(WORDLIST_DIR)/$$f $(WORDLIST_URL)/$$f; done
	cd $(WORDLIST_DIR) && sha256sum -c $(CURDIR)/tools/voa_corpus/wordlists.sha256

# Measures the whole cached corpus (read only) and rewrites the generated block of
# docs/reports/voa-corpus.md. About 90 s.
voa-corpus: voa-wordlists
	PYTHONPATH=tools uv run --no-project --with pyyaml python -m voa_corpus.analyze --report docs/reports/voa-corpus.md $(ARGS)

# The trimmed corpus (ADR-0008): the passages usable at a 5% cut, each with the lines the
# parser returned, the lines left and every removed line with its rule. Read-only on DATA_DIR; it
# writes $(TRIM_DIR) (default ~/sonari-trimmed/voa). About 90 s.
voa-trim: voa-wordlists
	PYTHONPATH=tools uv run --no-project --with pyyaml python -m voa_corpus.write_trimmed $(ARGS)

# Loads the trimmed corpus into content.sources as the `core` user (ADR-0010). Idempotent: run
# it again after a re-trim to add the new version and make it current. Starts the infra first.
SOURCES_FILE ?= $(HOME)/sonari-trimmed/voa/trimmed.jsonl
.PHONY: ingest-sources
ingest-sources: infra
	$(UV_RUN) services/core --env-file $(CURDIR)/.env python $(CURDIR)/scripts/ingest_sources.py $(SOURCES_FILE)

# What the text-less pages are: the seeded sample's labels (docs/reports/voa-missing-labels.tsv) with
# confidence intervals, and a census of the article text the parser never reads. Read only; about 60 s.
voa-missing:
	PYTHONPATH=tools uv run --no-project --with pyyaml python -m voa_corpus.missing $(ARGS)

# Topic-tagger evaluation (needs the owner's labels in tools/voa_inventory/labels/). The
# sample step is cheap; the evaluate step loads bge-m3 (2.3 GB download, ~3 GB RAM).
voa-sample:
	PYTHONPATH=tools uv run --no-project --with pyyaml python -m voa_inventory.sample

voa-evaluate:
	PYTHONPATH=tools uv run python -m voa_inventory.evaluate

# Needs network (model vocab from the Hugging Face hub) and espeak-ng; not part of CI.
check-phoneset:
	$(UV_RUN) spikes/gop python -m phoneset.check_vocab
	$(UV_RUN) spikes/gop python -m phoneset.roundtrip_test

fmt:
	@for s in $(SERVICES); do \
		$(UV_RUN) services/$$s ruff check --fix . && $(UV_RUN) services/$$s ruff format . || exit 1; \
	done
	uv run --no-project --with ruff ruff check --fix scripts tools spikes
	uv run --no-project --with ruff ruff format scripts tools spikes
