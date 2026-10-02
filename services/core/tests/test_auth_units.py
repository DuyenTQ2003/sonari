"""The pieces of the auth service on their own: password hashing, access tokens, Turnstile."""

import json

import argon2
import httpx
import pytest

from auth_fakes import FakeClock
from sonari_core.identity.captcha import CaptchaUnavailable, TurnstileVerifier
from sonari_core.identity.passwords import PasswordHasher
from sonari_core.identity.tokens import AccessTokenCodec, hash_refresh_token, new_refresh_token
from sonari_core.shared.errors import AppError

SECRET = "unit-test-jwt-secret-0123456789abcdef-xyz"


async def test_the_production_hasher_is_argon2id_with_adequate_cost() -> None:
    encoded = await PasswordHasher().hash("a password")

    parameters = argon2.extract_parameters(encoded)
    assert parameters.type is argon2.Type.ID
    assert parameters.memory_cost >= 19_456  # OWASP's minimum, in KiB
    assert parameters.time_cost >= 2


async def test_a_wrong_password_and_a_corrupt_hash_both_fail_cleanly() -> None:
    hasher = PasswordHasher()
    encoded = await hasher.hash("right")

    assert await hasher.verify(encoded, "right") is True
    assert await hasher.verify(encoded, "wrong") is False
    assert await hasher.verify("not-a-hash", "right") is False


def test_refresh_tokens_are_random_and_only_their_hash_is_kept() -> None:
    first, first_hash = new_refresh_token()
    second, _ = new_refresh_token()

    assert first != second
    assert len(first) >= 43  # 256 bits, url-safe base64
    assert first_hash == hash_refresh_token(first)
    assert first not in first_hash


def test_a_token_from_the_future_clock_is_expired_only_after_its_ttl() -> None:
    clock = FakeClock()
    codec = AccessTokenCodec(SECRET, 900, clock)
    token = codec.issue("user-1")

    assert codec.verify(token) == "user-1"
    clock.advance(900)
    with pytest.raises(AppError) as expired:
        codec.verify(token)
    assert expired.value.code == "token_expired"


def turnstile(handler: httpx.MockTransport) -> TurnstileVerifier:
    return TurnstileVerifier(
        "the-secret", "https://cf.test/siteverify", httpx.AsyncClient(transport=handler)
    )


async def test_turnstile_sends_secret_token_and_address_as_a_form() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"success": True})

    assert await turnstile(httpx.MockTransport(handler)).verify("tok", "203.0.113.7") is True

    (request,) = seen
    assert request.method == "POST"
    assert request.headers["content-type"] == "application/x-www-form-urlencoded"
    assert request.content == b"secret=the-secret&response=tok&remoteip=203.0.113.7"


@pytest.mark.parametrize("code", ["invalid-input-response", "timeout-or-duplicate", "bad-request"])
async def test_turnstile_rejects_a_bad_visitor_token(code: str) -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(200, json={"success": False, "error-codes": [code]})
    )

    assert await turnstile(transport).verify("tok", None) is False


@pytest.mark.parametrize("code", ["invalid-input-secret", "missing-input-secret", "internal-error"])
async def test_turnstile_treats_our_own_misconfiguration_as_unavailable(code: str) -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(200, json={"success": False, "error-codes": [code]})
    )

    with pytest.raises(CaptchaUnavailable):
        await turnstile(transport).verify("tok", None)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500),
        httpx.Response(200, content=b"<html>"),
        httpx.Response(200, content=json.dumps([]).encode()),
    ],
)
async def test_turnstile_failing_or_garbled_answers_are_unavailable_not_a_pass(
    response: httpx.Response,
) -> None:
    with pytest.raises(CaptchaUnavailable):
        await turnstile(httpx.MockTransport(lambda _: response)).verify("tok", None)


async def test_turnstile_network_errors_are_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(CaptchaUnavailable):
        await turnstile(httpx.MockTransport(handler)).verify("tok", None)
