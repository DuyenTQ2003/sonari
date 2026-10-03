"""FastAPI entry point for the speech service: `uvicorn sonari_speech.main:app`.

The model loads in a background task after startup, so `/healthz` answers at once and
`/readyz` turns green only when the model has loaded and run a warm-up inference.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from sonari_speech.errors import install_error_handlers
from sonari_speech.health import router as health_router
from sonari_speech.runtime.service import SpeechRuntime
from sonari_speech.settings import Settings


def _configure_logging(level: str) -> None:
    """Uvicorn configures only its own loggers; give ours a handler so INFO lines show."""
    logger = logging.getLogger("sonari_speech")
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)


def create_app(settings: Settings | None = None, runtime: SpeechRuntime | None = None) -> FastAPI:
    """Build the application; tests pass their own settings and a runtime with a fake model."""
    settings = settings or Settings()
    runtime = runtime or SpeechRuntime(settings)
    _configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        loader = asyncio.create_task(runtime.start())
        try:
            yield
        finally:
            loader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await loader
            runtime.close()

    app = FastAPI(title="sonari-speech", lifespan=lifespan)
    app.state.settings = settings
    app.state.runtime = runtime
    install_error_handlers(app)
    app.include_router(health_router)
    return app


app = create_app()
