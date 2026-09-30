SERVICES := core speech
UV_RUN := uv run --directory

LINT_TARGETS := $(SERVICES:%=lint-%)
TYPECHECK_TARGETS := $(SERVICES:%=typecheck-%)

# Every target is phony (none produces a file of that name).
# NOTE: make skips implicit (%) rule search for phony targets, so per-service targets
# must use static pattern rules ("targets: pattern:"), never a bare "lint-%:" rule;
# otherwise they silently become empty recipes ("Nothing to be done").
.PHONY: dev lint typecheck test test-core test-speech test-scripts test-tools check-phoneset fmt \
	lint-scripts $(LINT_TARGETS) $(TYPECHECK_TARGETS)

dev:
	@trap 'kill 0' INT TERM; \
	$(UV_RUN) services/core uvicorn sonari_core.main:app --reload --port 8000 & \
	$(UV_RUN) services/speech uvicorn sonari_speech.main:app --reload --port 8001 & \
	wait

lint: $(LINT_TARGETS) lint-scripts

$(LINT_TARGETS): lint-%:
	$(UV_RUN) services/$* ruff check .
	$(UV_RUN) services/$* ruff format --check .

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
.PHONY: voa-crawl voa-report
voa-crawl:
	PYTHONPATH=tools uv run --no-project --with pyyaml python -m voa_inventory.crawl $(ARGS)

voa-report:
	PYTHONPATH=tools uv run --no-project --with pyyaml python -m voa_inventory.report
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
