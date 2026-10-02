from fastapi.testclient import TestClient

from fakes import AppFactory, FakeCheck


def test_readyz_is_ready_when_every_dependency_answers(client: TestClient) -> None:
    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"mongo": "ok", "redis": "ok"}}


def test_readyz_fails_when_mongo_is_down(make_app: AppFactory) -> None:
    app = make_app(
        {
            "mongo": FakeCheck(error=ConnectionError("mongodb://core:secret@host: refused")),
            "redis": FakeCheck(),
        }
    )

    response = TestClient(app).get("/readyz")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "not_ready",
            "messageKey": "errors.not_ready",
            "details": {"checks": {"mongo": "down", "redis": "ok"}},
        }
    }
    assert "secret" not in response.text  # the driver's message may hold a connection string


def test_readyz_fails_when_redis_is_down(make_app: AppFactory) -> None:
    app = make_app({"mongo": FakeCheck(), "redis": FakeCheck(error=ConnectionError("refused"))})

    response = TestClient(app).get("/readyz")

    assert response.status_code == 503
    assert response.json()["error"]["details"]["checks"] == {"mongo": "ok", "redis": "down"}


def test_readyz_counts_a_dependency_that_hangs_as_down(make_app: AppFactory) -> None:
    """The driver's own wait is 30 s; readiness must answer within its timeout instead."""
    app = make_app({"mongo": FakeCheck(delay_s=5.0), "redis": FakeCheck()})

    response = TestClient(app).get("/readyz")

    assert response.status_code == 503
    assert response.json()["error"]["details"]["checks"]["mongo"] == "down"
