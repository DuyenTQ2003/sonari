"""The error envelope: every error response is `{"error": {code, messageKey, details}}`.

`code` is for programs, `messageKey` is for the client to look up in vi.json, and
`details` carries structured facts. None of them carries user-facing prose, and
validation details never echo the submitted values (they may hold a password).
"""

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from starlette.exceptions import HTTPException as StarletteHTTPException

from sonari_core.shared.message_keys import MessageKey

logger = logging.getLogger(__name__)


class ErrorBody(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    code: str
    message_key: MessageKey
    details: dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class AppError(Exception):
    """An expected failure that maps to a specific status and message key."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message_key: MessageKey,
        details: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message_key = message_key
        self.details = dict(details) if details else None
        self.headers = dict(headers) if headers else None


def error_response(
    status_code: int,
    code: str,
    message_key: MessageKey,
    details: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorEnvelope(
        error=ErrorBody(
            code=code, message_key=message_key, details=dict(details) if details else None
        )
    )
    return JSONResponse(
        body.model_dump(mode="json", by_alias=True), status_code=status_code, headers=headers
    )


_HTTP_KEYS: Mapping[int, tuple[str, MessageKey]] = {
    404: ("not_found", MessageKey.NOT_FOUND),
    405: ("method_not_allowed", MessageKey.METHOD_NOT_ALLOWED),
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message_key, exc.details, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [{"loc": list(error["loc"]), "type": error["type"]} for error in exc.errors()]
        return error_response(422, "validation_error", MessageKey.VALIDATION, {"fields": fields})

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, key = _HTTP_KEYS.get(exc.status_code, (f"http_{exc.status_code}", MessageKey.HTTP))
        return error_response(exc.status_code, code, key, headers=exc.headers)

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled exception", exc_info=exc)
        return error_response(500, "internal_error", MessageKey.INTERNAL)
