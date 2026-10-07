"""FastAPI entry point for the speech service: `uvicorn sonari_speech.main:app`.

The model and G2P load in background tasks after startup, so `/healthz` answers at once and
`/readyz` turns green only when the model has run a warm-up inference and G2P has loaded.
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
from sonari_speech.scoring.api import PronouncerFactory, Scorer, load_pronouncer
from sonari_speech.scoring.api import router as score_router
from sonari_speech.settings import Settings


def _configure_logging(level: str) -> None:
    """Uvicorn configures only its own loggers; give ours a handler so INFO lines show."""
    logger = logging.getLogger("sonari_speech")
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)


def create_app(
    settings: Settings | None = None,
    runtime: SpeechRuntime | None = None,
    pronouncer_factory: PronouncerFactory = load_pronouncer,
) -> FastAPI:
    """Build the application; tests pass their own settings, a fake model and a fake G2P."""
    settings = settings or Settings()
    runtime = runtime or SpeechRuntime(settings)
    scorer = Scorer(runtime, pronouncer_factory)
    _configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        loaders = [asyncio.create_task(runtime.start()), asyncio.create_task(scorer.start())]
        try:
            yield
        finally:
            for loader in loaders:
                loader.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await loader
            runtime.close()

    app = FastAPI(title="sonari-speech", lifespan=lifespan)
    app.state.settings = settings
    app.state.runtime = runtime
    app.state.scorer = scorer
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(score_router)
    return app


app = create_app()
