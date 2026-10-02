"""Helpers for the auth tests: calls to /v1/auth and reading what comes back."""

from fastapi.testclient import TestClient
from httpx import Response
from starlette.types import ASGIApp

from auth_fakes import AuthKit

EMAIL = "learner@example.com"
PASSWORD = "correct horse battery"


def register(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> Response:
    body = {"email": email, "password": password, "turnstileToken": "turnstile-ok"}
    return client.post("/v1/auth/register", json=body)


def login(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> Response:
    return client.post("/v1/auth/login", json={"email": email, "password": password})


def refresh_cookie(response: Response) -> str:
    """The raw refresh token set by a response."""
    return response.headers["set-cookie"].split(";")[0].split("=", 1)[1]


def replay_with(app: ASGIApp, token: str, ip: str = "testclient") -> Response:
    """Present a refresh token from a client that does not hold it in its cookie jar."""
    client = TestClient(
        app, base_url="https://testserver", client=(ip, 50000), raise_server_exceptions=False
    )
    return client.post("/v1/auth/refresh", headers={"Cookie": f"refresh_token={token}"})


def replay(kit: AuthKit, token: str) -> Response:
    return replay_with(kit.app, token)


def error(response: Response) -> dict[str, object]:
    body: dict[str, dict[str, object]] = response.json()
    return body["error"]
