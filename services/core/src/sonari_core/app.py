"""The application factory: wires settings, telemetry, error handling and the contexts.

This module sits above the bounded contexts, so it is the one place that imports all of
them. They never import it.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry.sdk.trace import TracerProvider

from sonari_core import analytics, content, gamification, identity, learning
from sonari_core.shared import health
from sonari_core.shared.contexts import ContextSpec, init_contexts
from sonari_core.shared.errors import install_error_handlers
from sonari_core.shared.logging import configure_logging
from sonari_core.shared.request_context import RequestIdMiddleware
from sonari_core.shared.resources import Resources, build_resources
from sonari_core.shared.settings import Settings
from sonari_core.shared.telemetry import setup_telemetry

CONTEXTS: tuple[ContextSpec, ...] = (
    identity.SPEC,
    content.SPEC,
    learning.SPEC,
    gamification.SPEC,
    analytics.SPEC,
)


def create_app(
    settings: Settings | None = None,
    *,
    resources: Resources | None = None,
    tracer_provider: TracerProvider | None = None,
) -> FastAPI:
    """Build the core application.

    `resources` and `tracer_provider` exist for tests; production passes neither, and the
    real MongoDB and Redis clients are then created when the application starts.
    """
    settings = settings or Settings()  # required fields come from the environment
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        active = resources or build_resources(settings)
        app.state.resources = active
        try:
            if active.mongo is not None:
                await init_contexts(active.mongo, CONTEXTS)
            yield
        finally:
            shutdown_telemetry()
            if resources is None:
                await active.close()

    app = FastAPI(title="sonari-core", lifespan=lifespan)
    app.state.settings = settings
    if resources is not None:
        app.state.resources = resources

    shutdown_telemetry = setup_telemetry(app, settings, tracer_provider)
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    app.include_router(health.router)
    return app
