import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from fakes import AppFactory
from sonari_core.shared.settings import Settings
from sonari_core.shared.telemetry import build_tracer_provider


@pytest.fixture
def exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def provider(exporter: InMemorySpanExporter) -> TracerProvider:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider


def test_requests_produce_a_server_span_when_telemetry_is_enabled(
    make_app: AppFactory, provider: TracerProvider, exporter: InMemorySpanExporter
) -> None:
    app = make_app(tracer_provider=provider, otel_enabled=True)

    @app.get("/probe/traced")
    async def traced() -> dict[str, str]:
        return {"ok": "yes"}

    with TestClient(app) as client:  # entering runs the lifespan; leaving undoes the patching
        client.get("/probe/traced")

    names = [span.name for span in exporter.get_finished_spans()]
    assert "GET /probe/traced" in names


def test_no_span_is_created_when_telemetry_is_disabled(
    make_app: AppFactory, provider: TracerProvider, exporter: InMemorySpanExporter
) -> None:
    app = make_app(tracer_provider=provider, otel_enabled=False)

    with TestClient(app) as client:
        client.get("/healthz")

    assert exporter.get_finished_spans() == ()


def test_probe_endpoints_are_not_traced(
    make_app: AppFactory, provider: TracerProvider, exporter: InMemorySpanExporter
) -> None:
    app = make_app(tracer_provider=provider, otel_enabled=True)

    with TestClient(app) as client:
        client.get("/healthz")
        client.get("/readyz")

    assert exporter.get_finished_spans() == ()


def test_spans_are_exported_only_when_an_otlp_endpoint_is_configured() -> None:
    base = Settings(mongo_uri="mongodb://x", redis_url="redis://x")  # type: ignore[call-arg]

    without_endpoint = build_tracer_provider(base)
    with_endpoint = build_tracer_provider(
        base.model_copy(update={"otlp_endpoint": "http://c:4318"})
    )

    processors = lambda p: p._active_span_processor._span_processors  # noqa: E731
    assert len(processors(without_endpoint)) == 0
    assert len(processors(with_endpoint)) == 1
