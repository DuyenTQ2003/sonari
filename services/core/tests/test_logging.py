import io
import json
import logging

from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider

from fakes import AppFactory
from sonari_core.shared.logging import configure_logging


def emit(message: str, **extra: object) -> dict[str, object]:
    """Log one line through the real configuration and parse it back."""
    stream = io.StringIO()
    configure_logging("INFO", stream)
    logging.getLogger("sonari_core.test").info(message, extra=extra)
    (line,) = stream.getvalue().splitlines()
    parsed: dict[str, object] = json.loads(line)
    return parsed


def test_a_log_line_is_one_json_object_with_the_standard_fields() -> None:
    entry = emit("lesson started", lesson="l1")

    assert entry["message"] == "lesson started"
    assert entry["level"] == "INFO"
    assert entry["logger"] == "sonari_core.test"
    assert entry["lesson"] == "l1"  # fields passed with extra= are kept
    assert str(entry["timestamp"]).endswith("+00:00")


def test_an_exception_is_logged_as_a_field_not_as_extra_lines() -> None:
    stream = io.StringIO()
    configure_logging("INFO", stream)

    try:
        raise ValueError("boom")
    except ValueError:
        logging.getLogger("sonari_core.test").exception("failed")

    (line,) = stream.getvalue().splitlines()
    assert "ValueError: boom" in json.loads(line)["exception"]


def test_calling_configure_twice_does_not_duplicate_lines() -> None:
    stream = io.StringIO()
    configure_logging("INFO", io.StringIO())
    configure_logging("INFO", stream)

    logging.getLogger("sonari_core.test").info("once")

    assert len(stream.getvalue().splitlines()) == 1


def test_log_lines_carry_the_trace_id_of_the_active_span() -> None:
    provider = TracerProvider()
    tracer = provider.get_tracer("test")

    with tracer.start_as_current_span("work") as span:
        entry = emit("inside a span")
        expected = span.get_span_context()

    assert entry["trace_id"] == format(expected.trace_id, "032x")
    assert entry["span_id"] == format(expected.span_id, "016x")
    assert "trace_id" not in emit("outside any span")


def test_log_lines_written_during_a_request_carry_its_request_id(make_app: AppFactory) -> None:
    app = make_app()
    stream = io.StringIO()

    @app.get("/probe/log")
    async def log_something() -> None:
        configure_logging("INFO", stream)
        logging.getLogger("sonari_core.test").info("inside the handler")

    TestClient(app).get("/probe/log", headers={"X-Request-ID": "req-42"})

    # The test client's own httpx log line goes through the same handler, so pick ours.
    entries = [json.loads(line) for line in stream.getvalue().splitlines()]
    (entry,) = [e for e in entries if e["logger"] == "sonari_core.test"]
    assert entry["request_id"] == "req-42"
