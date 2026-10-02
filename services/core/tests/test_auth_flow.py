"""Registration, login, refresh rotation, reuse detection and logout, over HTTP, against the
in-memory stores (so they run in CI). tests/integration/test_auth_live.py repeats the
important ones on real MongoDB and Redis."""

import time

import jwt

from auth_fakes import AuthKit
from auth_helpers import EMAIL, PASSWORD, error, login, refresh_cookie, register, replay
from sonari_core.identity.tokens import hash_refresh_token

# --- register and login ------------------------------------------------------------------


def test_register_signs_the_user_in(auth: AuthKit) -> None:
    response = register(auth.client())

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == EMAIL
    assert body["tokenType"] == "bearer"
    assert body["expiresIn"] == 900
    claims = jwt.decode(
        body["accessToken"],
        auth.settings.jwt_secret.get_secret_value(),
        ["HS256"],
        options={"verify_exp": False},
    )
    assert claims["sub"] == body["user"]["id"]
    assert response.headers["cache-control"] == "no-store"


def test_refresh_cookie_is_httponly_secure_lax_and_scoped_to_auth(auth: AuthKit) -> None:
    cookie = register(auth.client()).headers["set-cookie"].lower()

    assert cookie.startswith("refresh_token=")
    for attribute in ("httponly", "secure", "samesite=lax", "path=/v1/auth", "max-age=2592000"):
        assert attribute in cookie


def test_secrets_are_stored_hashed_never_raw(auth: AuthKit) -> None:
    response = register(auth.client())
    raw_refresh = refresh_cookie(response)

    (user,) = auth.users.by_email.values()
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash
    assert raw_refresh not in auth.tokens.records  # the store is keyed by the hash
    assert hash_refresh_token(raw_refresh) in auth.tokens.records
    assert PASSWORD not in response.text
    assert "password" not in response.text.lower()


def test_login_signs_in_with_a_new_session_family(auth: AuthKit) -> None:
    registered = register(auth.client())

    response = login(auth.client())

    assert response.status_code == 200
    first = auth.tokens.records[hash_refresh_token(refresh_cookie(registered))]
    second = auth.tokens.records[hash_refresh_token(refresh_cookie(response))]
    assert first.family_id != second.family_id


def test_email_is_case_insensitive(auth: AuthKit) -> None:
    assert register(auth.client(), "Learner@Example.com").status_code == 201

    assert login(auth.client(), "LEARNER@example.COM").status_code == 200
    duplicate = register(auth.client("10.0.0.9"), "learner@EXAMPLE.com")
    assert duplicate.status_code == 409
    assert error(duplicate)["messageKey"] == "errors.auth.email_taken"


def test_wrong_password_and_unknown_email_get_the_same_answer(auth: AuthKit) -> None:
    register(auth.client())

    wrong_password = login(auth.client(), password="not the password")
    unknown_email = login(auth.client(), email="nobody@example.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert error(wrong_password)["messageKey"] == "errors.auth.invalid_credentials"
    # The unknown email still paid for a password check, so it is not measurably faster.
    assert auth.hasher.decoy_checks == 1


def test_a_short_password_is_rejected_without_echoing_it(auth: AuthKit) -> None:
    response = register(auth.client(), password="p4ss")

    assert response.status_code == 422
    assert "p4ss" not in response.text
    assert not auth.users.by_email


# --- captcha -----------------------------------------------------------------------------


def test_failed_captcha_creates_no_account(auth: AuthKit) -> None:
    auth.captcha.passes = False

    response = register(auth.client())

    assert response.status_code == 400
    assert error(response)["messageKey"] == "errors.auth.captcha_failed"
    assert not auth.users.by_email


def test_unreachable_captcha_service_is_a_503_not_a_free_pass(auth: AuthKit) -> None:
    auth.captcha.unavailable = True

    response = register(auth.client())

    assert response.status_code == 503
    assert error(response)["messageKey"] == "errors.auth.captcha_unavailable"
    assert not auth.users.by_email


def test_the_token_and_client_address_reach_the_captcha_check(auth: AuthKit) -> None:
    register(auth.client("203.0.113.7"))

    assert auth.captcha.calls == [("turnstile-ok", "203.0.113.7")]


# --- access tokens -----------------------------------------------------------------------


def test_access_token_opens_me(auth: AuthKit) -> None:
    token = register(auth.client()).json()["accessToken"]

    response = auth.client().get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == EMAIL


def test_expired_access_token_is_refused_with_its_own_key(auth: AuthKit) -> None:
    token = register(auth.client()).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    auth.clock.advance(899)
    assert auth.client().get("/v1/auth/me", headers=headers).status_code == 200
    auth.clock.advance(2)
    response = auth.client().get("/v1/auth/me", headers=headers)

    assert response.status_code == 401
    assert error(response)["code"] == "token_expired"
    assert error(response)["messageKey"] == "errors.auth.token_expired"
    assert response.headers["www-authenticate"] == "Bearer"


def test_forged_missing_and_unsigned_tokens_are_refused(auth: AuthKit) -> None:
    now = int(time.time())
    claims = {"sub": "user-1", "iat": now, "exp": now + 900}
    forged = jwt.encode(claims, "some other secret, long enough to sign 0123", "HS256")
    unsigned = jwt.encode(claims, None, algorithm="none")
    client = auth.client()

    assert client.get("/v1/auth/me").status_code == 401
    for token in (forged, unsigned, "garbage"):
        response = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert error(response)["code"] == "token_invalid"


# --- refresh rotation, reuse detection, logout ------------------------------------------


def test_refresh_rotates_the_token(auth: AuthKit) -> None:
    client = auth.client()
    first = refresh_cookie(register(client))

    response = client.post("/v1/auth/refresh")  # the cookie jar sends the first token

    assert response.status_code == 200
    second = refresh_cookie(response)
    assert second != first
    assert auth.tokens.records[hash_refresh_token(first)].rotated_at is not None
    assert client.post("/v1/auth/refresh").status_code == 200  # the new token works too


def test_reusing_a_rotated_token_revokes_the_whole_family(auth: AuthKit) -> None:
    thief_copy = refresh_cookie(register(auth.client()))
    owner = auth.client()
    owner.cookies.set("refresh_token", thief_copy, path="/v1/auth")
    newest = refresh_cookie(owner.post("/v1/auth/refresh"))  # the owner rotates it
    other_login = login(auth.client("10.0.0.2"))  # a separate family of the same user

    replayed = replay(auth, thief_copy)  # the stolen, already-spent token

    assert replayed.status_code == 401
    assert error(replayed)["code"] == "refresh_reused"
    assert error(replayed)["messageKey"] == "errors.auth.session_invalid"
    # The family is dead, including the token the owner legitimately holds.
    assert replay(auth, newest).status_code == 401
    family = auth.tokens.records[hash_refresh_token(thief_copy)].family_id
    assert all(r.revoked_at is not None for r in auth.tokens.family(family))
    # Another session of the same user is untouched.
    assert replay(auth, refresh_cookie(other_login)).status_code == 200


def test_refresh_without_a_valid_cookie_is_refused(auth: AuthKit) -> None:
    register(auth.client())

    no_cookie = auth.client().post("/v1/auth/refresh")
    garbage = replay(auth, "not-a-token")

    for response in (no_cookie, garbage):
        assert response.status_code == 401
        assert error(response)["code"] == "refresh_invalid"


def test_an_expired_refresh_token_is_refused(auth: AuthKit) -> None:
    token = refresh_cookie(register(auth.client()))

    auth.clock.advance(30 * 24 * 3600 + 1)

    assert replay(auth, token).status_code == 401


def test_logout_ends_the_session_and_clears_the_cookie(auth: AuthKit) -> None:
    client = auth.client()
    token = refresh_cookie(register(client))

    response = client.post("/v1/auth/logout")

    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert replay(auth, token).status_code == 401


def test_logging_out_twice_or_without_a_session_is_fine(auth: AuthKit) -> None:
    client = auth.client()
    assert client.post("/v1/auth/logout").status_code == 204
    assert replay(auth, "garbage").status_code == 401
    register(client)
    assert client.post("/v1/auth/logout").status_code == 204
    assert client.post("/v1/auth/logout").status_code == 204
