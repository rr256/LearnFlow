"""Tests for composition-root wiring of the FastAPI application."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.composition.app_factory import create_app
from app.composition.config import AppEnv, Settings


def test_create_app_uses_injected_settings():
    settings = Settings(_env_file=None, app_env=AppEnv.test, api_port=9999)

    app = create_app(settings)

    assert app.state.settings is settings
    assert app.state.settings.app_env is AppEnv.test
    assert app.state.settings.api_port == 9999


def test_app_built_from_injected_settings_still_serves_health():
    app = create_app(Settings(_env_file=None, app_env=AppEnv.test))

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_invalid_configuration_fails_before_the_app_is_created(monkeypatch):
    """A bad value must raise during settings construction, not at request time."""
    monkeypatch.setenv("API_PORT", "70000")

    with pytest.raises(ValidationError):
        create_app()
