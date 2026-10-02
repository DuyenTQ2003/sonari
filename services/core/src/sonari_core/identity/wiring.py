"""Builds the real AuthService from settings and the process's Redis connection."""

from dataclasses import dataclass

import httpx
from redis.asyncio import Redis

from sonari_core.identity.captcha import TurnstileVerifier
from sonari_core.identity.passwords import PasswordHasher
from sonari_core.identity.service import AuthConfig, AuthService
from sonari_core.identity.stores import MongoTokenStore, MongoUserStore
from sonari_core.identity.tokens import AccessTokenCodec
from sonari_core.shared.ratelimit import RedisSlidingWindowLimiter
from sonari_core.shared.settings import Settings

TURNSTILE_TIMEOUT_S = 5.0


@dataclass
class IdentityRuntime:
    service: AuthService
    http: httpx.AsyncClient

    async def aclose(self) -> None:
        await self.http.aclose()


def build_identity(settings: Settings, redis: Redis) -> IdentityRuntime:
    http = httpx.AsyncClient(timeout=TURNSTILE_TIMEOUT_S)
    service = AuthService(
        users=MongoUserStore(),
        tokens=MongoTokenStore(),
        hasher=PasswordHasher(),
        codec=AccessTokenCodec(settings.jwt_secret.get_secret_value(), settings.access_token_ttl_s),
        limiter=RedisSlidingWindowLimiter(redis),
        captcha=TurnstileVerifier(
            settings.turnstile_secret.get_secret_value(), settings.turnstile_verify_url, http
        ),
        config=AuthConfig(
            access_ttl_s=settings.access_token_ttl_s,
            refresh_ttl_s=settings.refresh_token_ttl_s,
            register_limit=settings.register_limit,
            register_window_s=settings.register_window_s,
            login_ip_limit=settings.login_ip_limit,
            login_email_limit=settings.login_email_limit,
            login_window_s=settings.login_window_s,
        ),
    )
    return IdentityRuntime(service=service, http=http)
