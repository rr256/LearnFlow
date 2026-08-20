"""Validated application configuration.

Configuration lives in the composition root because it decides how the running
application is assembled. Domain and application code must never read environment
variables; they receive what they need through explicit arguments and ports.

Variable naming follows the three categories in ADR-009:

1. Core runtime -- ``APP_*`` and ``API_*``.
2. Capability -- ``<CAPABILITY>_PROVIDER`` selects an adapter, plus capability-level
   settings that are not vendor-specific.
3. Vendor -- ``<VENDOR>_<SETTING>`` configures one specific vendor.

Only the settings the backend actually uses today are defined here. Retrieval and
storage settings arrive with the code that reads them; the AI settings below
arrived with MNT-001, the first capability that asks a provider anything.

**No credential is defined here, and none is read.** The selected provider runs
locally and authenticates nothing (ADR-004), so there is no API key in this file,
in `.env.example`, or in the environment the backend expects. A cloud adapter
would add its own, as an explicit decision.
"""

import zoneinfo
from enum import StrEnum
from pathlib import Path

from pydantic import AnyHttpUrl, Field, PostgresDsn, field_validator
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


class AIProviderName(StrEnum):
    """Which adapter fulfils the `AIProvider` port.

    One member today. It exists as an enum rather than as a bare string so that
    selecting a provider is a validated choice at startup — an unknown value
    fails immediately with a named field, instead of surfacing much later as an
    unhandled branch in the composition root.

    Adding a member here is the visible decision ADR-004's mitigation calls for:
    a second provider means a second adapter, and if it is not local it means
    learner note text leaving the machine.
    """

    ollama = "ollama"


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

    # The timezone a learner record is created with. Core runtime under ADR-009:
    # it describes how this installation runs, selects no adapter, and names no
    # vendor. The default suits the learning program LearnFlow ships with; a
    # learner elsewhere sets it once rather than editing code.
    #
    # Validated as a real IANA zone, because a typo would otherwise surface much
    # later as a study plan whose days land in the wrong place.
    app_default_timezone: str = "Asia/Kolkata"

    # Capability-level setting under ADR-009: it survives a change of relational
    # database, unlike the POSTGRES_* values that configure the Compose service.
    #
    # Deliberately has no default. Every other setting here describes how this
    # process runs and has a safe universal value; a database URL names an
    # external system and carries credentials, so there is no honest default to
    # fall back on. A missing value fails at startup with a named field rather
    # than silently pointing the backend at the wrong database.
    database_url: PostgresDsn

    # Capability selection under ADR-009: it names which adapter fulfils the
    # `AIProvider` port without naming a vendor setting. Only `ollama` is
    # implemented, and its default keeps LearnFlow local unless someone changes
    # this deliberately.
    ai_provider: AIProviderName = AIProviderName.ollama

    # Capability-level, not vendor-level: how long any AI provider may take to
    # answer one question. It survives a change of provider, which is exactly
    # ADR-009's test for this category.
    #
    # Sixty seconds is generous on purpose. A local model on modest hardware is
    # slow rather than broken, and a timeout short enough to be tidy would report
    # a failure for a machine that was working. Bounded at both ends so a
    # mistyped value cannot mean "never give up".
    ai_request_timeout_seconds: float = Field(default=60.0, gt=0, le=600)

    # Vendor settings under ADR-009. `AnyHttpUrl` accepts `http` and `https`
    # only, which is a security boundary rather than tidiness: it is what stops a
    # `file://` value from turning the adapter's request into a local file read.
    ollama_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:11434")

    # No default model is invented beyond a common small one. A learner who has
    # pulled something else sets this once; a model that is not installed is
    # reported as such rather than guessed at.
    ollama_chat_model: str = Field(default="llama3.1:8b", min_length=1)

    @field_validator("app_log_level", mode="before")
    @classmethod
    def _normalise_log_level(cls, value: object) -> object:
        """Accept ``debug``, ``Debug``, or ``DEBUG`` and store the canonical form.

        ``case_sensitive=False`` in ``model_config`` governs variable *names*, not
        values, so value casing is normalised here.
        """
        return value.upper() if isinstance(value, str) else value

    @field_validator("app_default_timezone")
    @classmethod
    def _require_a_known_timezone(cls, value: str) -> str:
        """Reject anything the standard library cannot resolve to a real zone.

        ``ZoneInfo`` reads the system database, or ``tzdata`` where the platform
        ships none, so this accepts exactly the zones the application can later
        compute with.
        """
        try:
            zoneinfo.ZoneInfo(value)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(
                f"{value!r} is not a known IANA timezone, for example 'Asia/Kolkata'."
            ) from error
        return value


def load_settings() -> Settings:
    """Build settings from the environment and an optional local ``.env`` file.

    ``extra="ignore"`` keeps unrelated variables in a developer's shell or `.env`
    from failing startup, while unknown values still never reach the application.
    """
    return Settings()
