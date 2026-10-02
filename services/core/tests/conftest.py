"""Unit-test fixtures: an app wired to fake dependencies, so no MongoDB or Redis is needed."""

from collections.abc import Mapping

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider

from auth_fakes import AuthKit, build_auth_kit
from fakes import AppFactory, FakeCheck
from sonari_core.app import create_app
from sonari_core.shared.resources import ReadinessCheck, Resources
from sonari_core.shared.settings import Settings


@pytest.fixture
def settings() -> Settings:
    """Telemetry is off, as it is in every unit test."""
    return Settings(
        mongo_uri="mongodb://unused.invalid",
        redis_url="redis://unused.invalid",
        jwt_secret="unit-test-jwt-secret-0123456789abcdef-xyz",
        turnstile_secret="unit-test-turnstile-secret",
        otel_enabled=False,
        readiness_timeout_s=0.2,
    )


@pytest.fixture
def make_app(settings: Settings) -> AppFactory:
    def make(
        readiness: Mapping[str, ReadinessCheck] | None = None,
        *,
        tracer_provider: TracerProvider | None = None,
        otel_enabled: bool = False,
    ) -> FastAPI:
        checks = (
            readiness if readiness is not None else {"mongo": FakeCheck(), "redis": FakeCheck()}
        )
        return create_app(
            settings.model_copy(update={"otel_enabled": otel_enabled}),
            resources=Resources(readiness=checks),
            tracer_provider=tracer_provider,
        )

    return make


@pytest.fixture
def client(make_app: AppFactory) -> TestClient:
    # Unhandled errors must come back as the 500 envelope, not be re-raised into the test.
    return TestClient(make_app(), raise_server_exceptions=False)


@pytest.fixture
def auth(settings: Settings) -> AuthKit:
    return build_auth_kit(settings)
