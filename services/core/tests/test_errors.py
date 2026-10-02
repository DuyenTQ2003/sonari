import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from fakes import AppFactory
from sonari_core.shared.errors import AppError
from sonari_core.shared.message_keys import MessageKey


class Credentials(BaseModel):
    email: str
    age: int


def add_probe_routes(app: FastAPI) -> None:
    @app.get("/probe/app-error")
    async def app_error() -> None:
        raise AppError(409, "email_taken", MessageKey.HTTP, {"field": "email"}, {"X-Hint": "login"})

    @app.get("/probe/crash")
    async def crash() -> None:
        raise RuntimeError("database password is hunter2")

    @app.post("/probe/validate")
    async def validate(body: Credentials) -> None:
        return None


@pytest.fixture
def probed(make_app: AppFactory) -> TestClient:
    app = make_app()
    add_probe_routes(app)
    return TestClient(app, raise_server_exceptions=False)


def test_app_error_uses_the_envelope_with_a_camel_case_message_key(probed: TestClient) -> None:
    response = probed.get("/probe/app-error")

    assert response.status_code == 409
    assert response.json() == {
        "error": {"code": "email_taken", "messageKey": "errors.http", "details": {"field": "email"}}
    }
    assert response.headers["x-hint"] == "login"


def test_unknown_route_is_a_not_found_envelope(probed: TestClient) -> None:
    response = probed.get("/nowhere")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "not_found",
        "messageKey": "errors.not_found",
        "details": None,
    }


def test_wrong_method_is_a_method_not_allowed_envelope(probed: TestClient) -> None:
    response = probed.post("/healthz")

    assert response.status_code == 405
    assert response.json()["error"]["messageKey"] == "errors.method_not_allowed"


def test_validation_error_lists_fields_without_echoing_the_input(probed: TestClient) -> None:
    response = probed.post(
        "/probe/validate", json={"email": "a@b.co", "age": "p4ssw0rd-not-a-number"}
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["messageKey"] == "errors.validation"
    assert error["details"]["fields"] == [{"loc": ["body", "age"], "type": "int_parsing"}]
    assert "p4ssw0rd" not in response.text


def test_unhandled_exception_is_a_generic_500_that_leaks_nothing(
    probed: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        response = probed.get("/probe/crash")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "messageKey": "errors.internal", "details": None}
    }
    assert "hunter2" not in response.text
    assert any(record.exc_info for record in caplog.records)  # the cause is logged, not returned


def test_request_id_is_echoed_or_generated(probed: TestClient) -> None:
    echoed = probed.get("/healthz", headers={"X-Request-ID": "abc-123"})
    generated = probed.get("/healthz")
    forged = probed.get("/healthz", headers={"X-Request-ID": 'x"}\n{"level":"CRITICAL'})

    assert echoed.headers["x-request-id"] == "abc-123"
    assert len(generated.headers["x-request-id"]) == 32
    assert forged.headers["x-request-id"] != 'x"}\n{"level":"CRITICAL'
