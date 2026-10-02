"""Liveness (`/healthz`) and readiness (`/readyz`).

Liveness says the process is up and touches nothing else. Readiness pings every
dependency, each with its own timeout, so a dead Mongo makes it answer 503 in seconds.
"""

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from sonari_core.shared.errors import ErrorEnvelope, error_response
from sonari_core.shared.message_keys import MessageKey
from sonari_core.shared.resources import ReadinessCheck, Resources

logger = logging.getLogger(__name__)
router = APIRouter()

Verdict = Literal["ok", "down"]


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, Verdict]


@router.get("/healthz", response_model=HealthResponse)
async def healthz(request: Request) -> HealthResponse:
    return HealthResponse(status="ok", service=request.app.state.settings.service_name)


@router.get(
    "/readyz",
    response_model=None,
    responses={200: {"model": ReadyResponse}, 503: {"model": ErrorEnvelope}},
)
async def readyz(request: Request) -> JSONResponse:
    resources: Resources = request.app.state.resources
    timeout: float = request.app.state.settings.readiness_timeout_s

    outcomes = await asyncio.gather(
        *(_run(name, check, timeout) for name, check in resources.readiness.items())
    )
    checks = dict(outcomes)
    if all(verdict == "ok" for verdict in checks.values()):
        return JSONResponse(ReadyResponse(status="ready", checks=checks).model_dump())
    return error_response(503, "not_ready", MessageKey.NOT_READY, {"checks": checks})


async def _run(name: str, check: ReadinessCheck, timeout: float) -> tuple[str, Verdict]:
    try:
        await asyncio.wait_for(check.ping(), timeout)
    except Exception as exc:
        # The class name is enough for the log; the message could hold a connection string.
        logger.warning(
            "readiness check failed", extra={"dependency": name, "reason": type(exc).__name__}
        )
        return name, "down"
    return name, "ok"
