# syntax=docker/dockerfile:1
# Build from this directory:  docker build -t sonari-speech services/speech
# With the model baked in:    docker build --build-arg MODEL_URL=https://... -t sonari-speech services/speech
# Without MODEL_URL the image has no model; mount one at /models (the service checks its SHA-256).

FROM python:3.11-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.5.31 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.11-slim-bookworm
# ffmpeg decodes the browsers' recordings (WebM/Opus, MP4/AAC, Ogg, WAV).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --home-dir /nonexistent sonari
COPY --from=build /app /app
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    SPEECH_MODEL_DIR=/models \
    DATA_DIR=/app

# G2P reads the cmudict corpus from $DATA_DIR/nltk_data and never downloads at runtime.
RUN python -m sonari_speech.g2p.backend /app/nltk_data

# Fetch the pinned model at build time; the checksum in models.yaml must match.
ARG MODEL_URL=""
RUN mkdir -p /models \
    && if [ -n "$MODEL_URL" ]; then \
         python -m sonari_speech.runtime.weights --url "$MODEL_URL" --dir /models; \
       else echo "no MODEL_URL: the image has no model, mount one at /models"; fi

USER sonari
EXPOSE 8001
CMD ["uvicorn", "sonari_speech.main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers"]
