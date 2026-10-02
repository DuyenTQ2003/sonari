"""Process configuration, read from the environment (see .env.example)."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings of the core process.

    The environment variable names match .env.example, so one `.env` serves compose and
    the service. The Mongo URI must be the `core` service user's, never the root user's.
    """

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    service_name: str = "core"
    log_level: str = "INFO"

    mongo_uri: str = Field(validation_alias="MONGO_URI_CORE")
    # Fail a request in seconds, not in the driver's default of 30 s, when Mongo is down.
    mongo_server_selection_timeout_ms: int = 5000
    redis_url: str = Field(validation_alias="REDIS_URL")

    # How long one readiness check may take before that dependency counts as down.
    readiness_timeout_s: float = 2.0

    # Spans are always created when enabled, so logs carry trace ids even without a
    # collector. They are exported only when an OTLP endpoint is configured.
    otel_enabled: bool = Field(default=True, validation_alias="OTEL_ENABLED")
    otlp_endpoint: str | None = Field(default=None, validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT")
