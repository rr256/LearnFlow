"""Unit tests for validated backend configuration."""

import pytest
from pydantic import ValidationError

from app.composition.config import AppEnv, LogLevel, Settings


def test_defaults_apply_when_nothing_is_configured():
    settings = Settings(_env_file=None)

    assert settings.app_env is AppEnv.local
    assert settings.app_log_level is LogLevel.info
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    assert settings.app_default_timezone == "Asia/Kolkata"


def test_database_url_is_required(monkeypatch):
    """A database URL names an external system, so it has no safe default."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    assert "database_url" in str(excinfo.value)


def test_database_url_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://learner:secret@db.internal:6543/learnflow"
    )

    settings = Settings(_env_file=None)

    # PostgresDsn is a multi-host URL, so host details come from hosts().
    host = settings.database_url.hosts()[0]
    assert host["host"] == "db.internal"
    assert host["port"] == 6543
    assert settings.database_url.path == "/learnflow"
    assert settings.database_url.scheme == "postgresql+psycopg"


@pytest.mark.parametrize(
    "value",
    [
        "mysql://learnflow:learnflow@127.0.0.1:3306/learnflow",
        "sqlite:///learnflow.db",
        "redis://127.0.0.1:6379/0",
        "not-a-url",
        "",
    ],
)
def test_non_postgresql_database_url_is_rejected(monkeypatch, value):
    """ADR-003 selects PostgreSQL; another backend must not start silently."""
    monkeypatch.setenv("DATABASE_URL", value)

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    assert "database_url" in str(excinfo.value)


def test_environment_variables_override_defaults(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("APP_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_PORT", "9001")

    settings = Settings(_env_file=None)

    assert settings.app_env is AppEnv.staging
    assert settings.app_log_level is LogLevel.debug
    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 9001


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("DEBUG", LogLevel.debug),
        ("debug", LogLevel.debug),
        ("Debug", LogLevel.debug),
        ("INFO", LogLevel.info),
        ("info", LogLevel.info),
        ("WARNING", LogLevel.warning),
        ("warning", LogLevel.warning),
        ("ErRoR", LogLevel.error),
        ("critical", LogLevel.critical),
    ],
)
def test_log_level_is_accepted_in_any_casing(monkeypatch, configured, expected):
    monkeypatch.setenv("APP_LOG_LEVEL", configured)

    settings = Settings(_env_file=None)

    assert settings.app_log_level is expected
    assert settings.app_log_level.value == expected.value.upper()


@pytest.mark.parametrize("value", ["verbose", "trace", "", "warn"])
def test_invalid_log_level_is_rejected(monkeypatch, value):
    monkeypatch.setenv("APP_LOG_LEVEL", value)

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    assert "app_log_level" in str(excinfo.value)


@pytest.mark.parametrize("value", ["production ", "prod", "development", ""])
def test_invalid_app_env_is_rejected(monkeypatch, value):
    monkeypatch.setenv("APP_ENV", value)

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    assert "app_env" in str(excinfo.value)


@pytest.mark.parametrize("value", ["0", "65536", "-1", "not-a-port"])
def test_invalid_api_port_is_rejected(monkeypatch, value):
    monkeypatch.setenv("API_PORT", value)

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    assert "api_port" in str(excinfo.value)


def test_port_boundaries_are_accepted(monkeypatch):
    """1 and 65535 are valid; the range check must not be off by one."""
    for port in (1, 65535):
        monkeypatch.setenv("API_PORT", str(port))
        assert Settings(_env_file=None).api_port == port


@pytest.mark.parametrize("value", ["Asia/Kolkata", "UTC", "Europe/Berlin", "America/New_York"])
def test_a_known_timezone_is_accepted(monkeypatch, value):
    monkeypatch.setenv("APP_DEFAULT_TIMEZONE", value)

    assert Settings(_env_file=None).app_default_timezone == value


@pytest.mark.parametrize("value", ["Asia/Calcutta_", "IST", "+05:30", "", "Mars/Olympus"])
def test_an_unknown_timezone_is_rejected(monkeypatch, value):
    """A typo would otherwise surface as a study plan whose days land a day out."""
    monkeypatch.setenv("APP_DEFAULT_TIMEZONE", value)

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    assert "app_default_timezone" in str(excinfo.value)
