"""ASGI entry point: `uvicorn sonari_core.main:app_factory --factory`.

A factory, not a module-level `app`, so importing this module needs no environment.
"""

from fastapi import FastAPI

from sonari_core.app import create_app


def app_factory() -> FastAPI:
    return create_app()
