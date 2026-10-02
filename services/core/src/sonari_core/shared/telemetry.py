"""OpenTelemetry: traces for FastAPI, PyMongo (Beanie's driver) and Redis.

Disabled with `OTEL_ENABLED=false`, which is what the tests do. Spans are created
whenever it is enabled; they leave the process only when an OTLP endpoint is configured.
"""

from collections.abc import Callable

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from sonari_core.shared.settings import Settings

# Orchestrator probes run every few seconds; tracing them only adds noise.
_UNTRACED_PATHS = "healthz,readyz"

Shutdown = Callable[[], None]


def _no_op() -> None:
    return None


def build_tracer_provider(settings: Settings) -> TracerProvider:
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: settings.service_name}))
    if settings.otlp_endpoint:
        endpoint = f"{settings.otlp_endpoint.rstrip('/')}/v1/traces"
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    return provider


def setup_telemetry(
    app: FastAPI, settings: Settings, tracer_provider: TracerProvider | None = None
) -> Shutdown:
    """Instrument `app` and the database clients created afterwards; return the undo.

    Call this before the Mongo and Redis clients are created: the PyMongo instrumentation
    attaches a listener that only clients built later pick up. A caller-supplied provider
    (tests) is used as is and is not made the global one.

    PyMongo's instrumentation can be paused but not removed, and it keeps the tracer of the
    first provider it was given. So a process has one provider for MongoDB spans: fine for
    the service, which instruments once, but tests that need MongoDB spans run in their own
    process.
    """
    if not settings.otel_enabled:
        return _no_op

    owns_provider = tracer_provider is None
    provider = tracer_provider or build_tracer_provider(settings)
    if owns_provider:
        trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls=_UNTRACED_PATHS)
    PymongoInstrumentor().instrument(tracer_provider=provider)
    RedisInstrumentor().instrument(tracer_provider=provider)

    def shutdown() -> None:
        FastAPIInstrumentor.uninstrument_app(app)
        PymongoInstrumentor().uninstrument()
        RedisInstrumentor().uninstrument()
        if owns_provider:
            provider.shutdown()

    return shutdown
