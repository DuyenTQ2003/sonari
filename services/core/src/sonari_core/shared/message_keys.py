"""Message keys the API returns instead of text.

The Vietnamese copy for each key lives in apps/web/messages/vi.json; a test fails when a
key here has no entry there. Keys are dotted paths into that file, so no key may be a
prefix of another.
"""

from enum import StrEnum


class MessageKey(StrEnum):
    INTERNAL = "errors.internal"
    NOT_FOUND = "errors.not_found"
    METHOD_NOT_ALLOWED = "errors.method_not_allowed"
    VALIDATION = "errors.validation"
    NOT_READY = "errors.not_ready"
    HTTP = "errors.http"
    AUTH_INVALID_CREDENTIALS = "errors.auth.invalid_credentials"
    AUTH_EMAIL_TAKEN = "errors.auth.email_taken"
    AUTH_TOKEN_EXPIRED = "errors.auth.token_expired"
    AUTH_TOKEN_INVALID = "errors.auth.token_invalid"
    AUTH_SESSION_INVALID = "errors.auth.session_invalid"
    AUTH_RATE_LIMITED = "errors.auth.rate_limited"
    AUTH_CAPTCHA_FAILED = "errors.auth.captcha_failed"
    AUTH_CAPTCHA_UNAVAILABLE = "errors.auth.captcha_unavailable"
