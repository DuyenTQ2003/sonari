from fastapi.testclient import TestClient

from fakes import AppFactory, FakeCheck


def test_healthz_reports_ok(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "core"}


def test_healthz_stays_up_when_a_dependency_is_down(make_app: AppFactory) -> None:
    """Liveness must not depend on MongoDB or Redis, or an outage would restart the pods."""
    app = make_app({"mongo": FakeCheck(error=RuntimeError("down"))})

    assert TestClient(app).get("/healthz").status_code == 200
