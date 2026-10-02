"""Cloudflare Turnstile verification for registration."""

import logging
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

# The secret or the request is wrong: not the visitor's fault, and retrying cannot help.
_SERVER_SIDE_ERRORS = frozenset({"missing-input-secret", "invalid-input-secret", "internal-error"})


class CaptchaUnavailable(Exception):
    """The check could not be made (Cloudflare unreachable or misconfigured)."""


class CaptchaVerifier(Protocol):
    async def verify(self, token: str, remote_ip: str | None) -> bool:
        """True for a valid token, False for a bad one; raises CaptchaUnavailable."""
        ...


class TurnstileVerifier:
    def __init__(self, secret: str, verify_url: str, client: httpx.AsyncClient) -> None:
        self._secret = secret
        self._url = verify_url
        self._client = client

    async def verify(self, token: str, remote_ip: str | None) -> bool:
        form = {"secret": self._secret, "response": token}
        if remote_ip:
            form["remoteip"] = remote_ip
        try:
            response = await self._client.post(self._url, data=form)
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("siteverify did not return a JSON object")
        except (httpx.HTTPError, ValueError) as error:
            logger.error(
                "turnstile verification unavailable", extra={"reason": type(error).__name__}
            )
            raise CaptchaUnavailable from error

        if body.get("success") is True:
            return True
        codes = set(body.get("error-codes", []))
        if codes & _SERVER_SIDE_ERRORS:
            logger.error("turnstile rejected our request", extra={"error_codes": sorted(codes)})
            raise CaptchaUnavailable
        return False
