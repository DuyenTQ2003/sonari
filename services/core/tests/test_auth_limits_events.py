"""Rate limits on register and login, and the UserRegistered event."""

import json
import logging
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest
from jsonschema import Draft202012Validator

from auth_fakes import AuthKit
from auth_helpers import PASSWORD, error, login, register
from sonari_core.identity.events import UserRegistered

SCHEMA = (
    Path(__file__).resolve().parents[3]
    / "packages/contracts/schema/events/user-registered.schema.json"
)


# --- rate limits -------------------------------------------------------------------------


def test_register_is_limited_per_address_and_the_limit_slides(auth: AuthKit) -> None:
    client = auth.client()
    for n in range(5):
        assert register(client, f"user{n}@example.com").status_code == 201

    blocked = register(client, "user5@example.com")

    assert blocked.status_code == 429
    assert error(blocked)["code"] == "rate_limited"
    assert error(blocked)["messageKey"] == "errors.auth.rate_limited"
    assert blocked.headers["retry-after"] == "3600"
    assert len(auth.captcha.calls) == 5  # refused before spending a captcha check
    assert "user5@example.com" not in auth.users.by_email

    auth.clock.advance(3601)
    assert register(client, "user5@example.com").status_code == 201


def test_another_address_is_not_blocked_by_the_first(auth: AuthKit) -> None:
    for n in range(6):
        register(auth.client("198.51.100.1"), f"user{n}@example.com")

    assert register(auth.client("198.51.100.2"), "other@example.com").status_code == 201


def test_login_is_limited_per_email_even_across_addresses(auth: AuthKit) -> None:
    register(auth.client("10.0.0.1"))
    for n in range(5):  # five wrong passwords, each from a different address
        assert login(auth.client(f"10.1.0.{n}"), password="wrong").status_code == 401

    blocked = login(auth.client("10.1.0.99"))  # even the right password, from a new address

    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1


def test_login_is_limited_per_address_across_emails(auth: AuthKit) -> None:
    client = auth.client("10.2.0.1")
    for n in range(10):
        assert login(client, email=f"guess{n}@example.com").status_code == 401

    assert login(client, email="guess10@example.com").status_code == 429


def test_refused_attempts_do_not_extend_the_lockout(auth: AuthKit) -> None:
    """Hammering a victim's email must not keep them locked out beyond one window."""
    register(auth.client("10.0.0.1"))
    for n in range(5):
        login(auth.client(f"10.3.0.{n}"), password="wrong")
    for n in range(20):  # the attacker keeps trying while blocked
        assert login(auth.client(f"10.4.0.{n}"), password="wrong").status_code == 429

    auth.clock.advance(901)

    assert login(auth.client("10.0.0.1")).status_code == 200


# --- UserRegistered ----------------------------------------------------------------------


def test_registration_publishes_one_valid_event_without_personal_data(auth: AuthKit) -> None:
    response = register(auth.client())

    ((event_type, payload),) = auth.publisher.events
    assert event_type == "UserRegistered"
    assert payload["userId"] == response.json()["user"]["id"]
    assert Draft202012Validator(json.loads(SCHEMA.read_text())).is_valid(payload)
    UUID(payload["eventId"])
    datetime.fromisoformat(payload["occurredAt"])
    assert "learner@example.com" not in json.dumps(payload)
    assert PASSWORD not in json.dumps(payload)


def test_logging_in_publishes_nothing(auth: AuthKit) -> None:
    register(auth.client())
    login(auth.client())

    assert len(auth.publisher.events) == 1


def test_a_failed_publish_does_not_undo_the_registration(
    auth: AuthKit, caplog: pytest.LogCaptureFixture
) -> None:
    auth.publisher.fail = True

    with caplog.at_level(logging.ERROR):
        response = register(auth.client())

    assert response.status_code == 201
    assert login(auth.client()).status_code == 200
    assert any("could not publish UserRegistered" in r.getMessage() for r in caplog.records)


def test_the_hand_written_model_matches_the_contract_schema() -> None:
    schema = json.loads(SCHEMA.read_text())
    model = UserRegistered.model_json_schema(by_alias=True)

    assert set(model["required"]) >= set(schema["required"]) - {"version"}  # version has a default
    assert set(model["properties"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False


def test_the_schema_rejects_extra_fields_and_missing_ones(auth: AuthKit) -> None:
    register(auth.client())
    ((_, payload),) = auth.publisher.events
    validator = Draft202012Validator(json.loads(SCHEMA.read_text()))

    assert not validator.is_valid({**payload, "email": "learner@example.com"})
    assert not validator.is_valid({k: v for k, v in payload.items() if k != "userId"})
    assert not validator.is_valid({**payload, "version": 2})
