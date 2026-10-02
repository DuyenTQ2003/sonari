import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from sonari_core.shared.contexts import CORE_CONTEXTS, Context, ContextSpec, init_contexts
from sonari_core.shared.message_keys import MessageKey
from sonari_core.shared.settings import Settings

VI_JSON = Path(__file__).resolve().parents[3] / "apps" / "web" / "messages" / "vi.json"


def test_settings_read_the_variable_names_used_in_env_example(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MONGO_URI_CORE", "mongodb://core:pw@localhost:27017/?authSource=admin")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.setenv("JWT_SECRET", "j" * 32)
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "turnstile-secret")

    settings = Settings()

    assert settings.mongo_uri.startswith("mongodb://core:")
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.otlp_endpoint == "http://collector:4318"
    assert settings.otel_enabled is True


def test_settings_refuse_to_start_without_a_mongo_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MONGO_URI_CORE", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET", "j" * 32)
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "turnstile-secret")

    with pytest.raises(ValidationError, match="MONGO_URI_CORE"):
        Settings()


def required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONGO_URI_CORE", "mongodb://core:pw@localhost:27017")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET", "j" * 32)
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "turnstile-secret")


@pytest.mark.parametrize("missing", ["JWT_SECRET", "TURNSTILE_SECRET_KEY"])
def test_settings_refuse_to_start_without_an_auth_secret(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    """There is no default signing key: a missing one must stop the service."""
    required_environment(monkeypatch)
    monkeypatch.delenv(missing)

    with pytest.raises(ValidationError, match=missing):
        Settings()


def test_settings_refuse_a_jwt_secret_that_is_too_short(monkeypatch: pytest.MonkeyPatch) -> None:
    required_environment(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "too-short")

    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings()


def test_secrets_do_not_appear_when_settings_are_printed_or_logged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    required_environment(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "s3cr3t-signing-key-0123456789abcdef-xyz")

    shown = repr(Settings()) + str(Settings())

    assert "s3cr3t-signing-key" not in shown
    assert "turnstile-secret" not in shown


def test_there_are_exactly_the_seven_contexts_of_adr_0001() -> None:
    assert {context.value for context in Context} == {
        "identity",
        "content",
        "learning",
        "gamification",
        "speech",
        "tutor",
        "analytics",
    }


def test_the_core_process_hosts_five_of_them() -> None:
    assert {context.value for context in CORE_CONTEXTS} == {
        "identity",
        "content",
        "learning",
        "gamification",
        "analytics",
    }


@pytest.mark.parametrize("foreign", [Context.SPEECH, Context.TUTOR])
def test_core_refuses_to_initialise_a_context_it_does_not_host(foreign: Context) -> None:
    # The client is never touched: the check runs before any database is opened.
    with pytest.raises(ValueError, match=foreign.value):
        asyncio.run(init_contexts(None, [ContextSpec(foreign)]))  # type: ignore[arg-type]


def test_every_message_key_has_a_vietnamese_entry() -> None:
    messages = json.loads(VI_JSON.read_text(encoding="utf-8"))

    for key in MessageKey:
        node = messages
        for part in key.value.split("."):
            assert part in node, f"{key.value} is missing from vi.json"
            node = node[part]
        assert isinstance(node, str)
        assert node.strip(), f"{key.value} is empty in vi.json"


def test_no_message_key_is_a_prefix_of_another() -> None:
    """Keys are paths into a JSON tree, so one key cannot be both a text and a branch."""
    keys = [key.value for key in MessageKey]

    for key in keys:
        assert not any(other.startswith(key + ".") for other in keys)
