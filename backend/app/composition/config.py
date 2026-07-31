"""Validated application configuration.

Configuration lives in the composition root because it decides how the running
application is assembled. Domain and application code must never read environment
variables; they receive what they need through explicit arguments and ports.

Variable naming follows the three categories in ADR-009:

1. Core runtime -- ``APP_*`` and ``API_*``.
2. Capability -- ``<CAPABILITY>_PROVIDER`` selects an adapter, plus capability-level
   settings that are not vendor-specific.
3. Vendor -- ``<VENDOR>_<SETTING>`` configures one specific vendor.

Only the settings the backend actually uses today are defined here. AI, retrieval,
and storage settings arrive with the code that reads them.
"""

from enum import StrEnum
from pathlib import Path

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class AppEnv(StrEnum):
    """Deployment environment the backend is running as."""

    local = "local"
    test = "test"
    staging = "staging"
    production = "production"


class LogLevel(StrEnum):
    """Standard library logging levels.

    Members store the canonical uppercase form. Input is accepted in any casing and
    normalised by ``Settings``; see ``_normalise_log_level``.
    """

    debug = "DEBUG"
    info = "INFO"
    warning = "WARNING"
    error = "ERROR"
    critical = "CRITICAL"


class Settings(BaseSettings):
    """Backend configuration, validated at construction.

    Invalid values raise ``pydantic.ValidationError`` before the application is
    created, so the process fails fast with a safe, actionable message rather than
    starting in an unusable state.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: AppEnv = AppEnv.local
    app_log_level: LogLevel = LogLevel.info
    api_host: str = Field(default="127.0.0.1", min_length=1)
    api_port: int = Field(default=8000, ge=1, le=65535)

    # Capability-level setting under ADR-009: it survives a change of relational
    # database, unlike the POSTGRES_* values that configure the Compose service.
    #
    # Deliberately has no default. Every other setting here describes how this
    # process runs and has a safe universal value; a database URL names an
    # external system and carries credentials, so there is no honest default to
    # fall back on. A missing value fails at startup with a named field rather
    # than silently pointing the backend at the wrong database.
    database_url: PostgresDsn

    @field_validator("app_log_level", mode="before")
    @classmethod
    def _normalise_log_level(cls, value: object) -> object:
        """Accept ``debug``, ``Debug``, or ``DEBUG`` and store the canonical form.

        ``case_sensitive=False`` in ``model_config`` governs variable *names*, not
        values, so value casing is normalised here.
        """
        return value.upper() if isinstance(value, str) else value


def load_settings() -> Settings:
    """Build settings from the environment and an optional local ``.env`` file.

    ``extra="ignore"`` keeps unrelated variables in a developer's shell or `.env`
    from failing startup, while unknown values still never reach the application.
    """
    return Settings()
