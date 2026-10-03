"""Liveness (`/healthz`) and readiness (`/readyz`).

Liveness only says the process is up. Readiness says the model is loaded and warmed up and
ffmpeg can be started, so an orchestrator sends no traffic before it can be served.
"""

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from sonari_speech.errors import ErrorEnvelope, MessageKey, error_response
from sonari_speech.runtime.audio import ffmpeg_available
from sonari_speech.runtime.service import SpeechRuntime

router = APIRouter()

Verdict = Literal["ok", "down"]


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, Verdict]


@router.get("/healthz", response_model=HealthResponse)
def healthz(request: Request) -> HealthResponse:
    return HealthResponse(status="ok", service=request.app.state.settings.service_name)


@router.get(
    "/readyz",
    response_model=None,
    responses={200: {"model": ReadyResponse}, 503: {"model": ErrorEnvelope}},
)
def readyz(request: Request) -> JSONResponse:
    runtime: SpeechRuntime = request.app.state.runtime
    checks: dict[str, Verdict] = {
        "model": "ok" if runtime.ready else "down",
        "ffmpeg": "ok" if ffmpeg_available(runtime.settings) else "down",
    }
    if all(verdict == "ok" for verdict in checks.values()):
        return JSONResponse(ReadyResponse(status="ready", checks=checks).model_dump())
    return error_response(503, "not_ready", MessageKey.NOT_READY, {"checks": checks})
