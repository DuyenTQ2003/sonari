"""FastAPI entry point for the speech service."""

from fastapi import FastAPI
from pydantic import BaseModel

SERVICE_NAME = "speech"


class HealthResponse(BaseModel):
    """Liveness probe payload."""

    status: str
    service: str


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    app = FastAPI(title="sonari-speech")

    @app.get("/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return HealthResponse(status="ok", service=SERVICE_NAME)

    return app


app = create_app()
