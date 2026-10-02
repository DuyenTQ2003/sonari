"""A request id for every request: read from `X-Request-ID` or generated, then echoed back.

It is stored in a context variable so log records written anywhere during the request
carry it, even when no trace is active.
"""

import uuid
from contextvars import ContextVar

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADER = "x-request-id"
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    return _request_id.get()


class RequestIdMiddleware:
    """Pure ASGI middleware, so it neither buffers bodies nor breaks context variables."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(HEADER.encode(), b"").decode("latin-1")
        request_id = incoming if _is_acceptable(incoming) else uuid.uuid4().hex
        token = _request_id.set(request_id)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            _request_id.reset(token)


def _is_acceptable(value: str) -> bool:
    """Accept a caller's id only if it is short and plain, so it cannot forge log lines."""
    return 0 < len(value) <= 64 and value.isascii() and value.replace("-", "").isalnum()
