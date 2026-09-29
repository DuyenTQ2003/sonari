SERVICES := core speech
UV_RUN := uv run --directory

.PHONY: dev lint typecheck test test-core test-speech test-scripts fmt lint-scripts \
	$(SERVICES:%=lint-%) $(SERVICES:%=typecheck-%)

dev:
	@trap 'kill 0' INT TERM; \
	$(UV_RUN) services/core uvicorn sonari_core.main:app --reload --port 8000 & \
	$(UV_RUN) services/speech uvicorn sonari_speech.main:app --reload --port 8001 & \
	wait

lint: $(SERVICES:%=lint-%) lint-scripts

lint-%:
	$(UV_RUN) services/$* ruff check .
	$(UV_RUN) services/$* ruff format --check .

lint-scripts:
	uv run --no-project --with ruff ruff check scripts
	uv run --no-project --with ruff ruff format --check scripts
	uv run --no-project python scripts/check_no_vietnamese.py services scripts

typecheck: $(SERVICES:%=typecheck-%)

typecheck-%:
	$(UV_RUN) services/$* mypy

test: test-core test-speech test-scripts

test-core:
	$(UV_RUN) services/core pytest

# Must stay under 10 s and must not load model weights.
test-speech:
	$(UV_RUN) services/speech pytest

test-scripts:
	uv run --no-project --with pytest pytest -q scripts/tests

fmt:
	@for s in $(SERVICES); do \
		$(UV_RUN) services/$$s ruff check --fix . && $(UV_RUN) services/$$s ruff format . || exit 1; \
	done
	uv run --no-project --with ruff ruff check --fix scripts
	uv run --no-project --with ruff ruff format scripts
