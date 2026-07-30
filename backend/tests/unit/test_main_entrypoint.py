"""Tests for the ``python -m app.main`` execution path.

Uvicorn is patched so no server is started; these tests verify only that
configuration reaches it correctly.
"""

import app.main as main_module
from app.composition.config import AppEnv, LogLevel, Settings


def _capture_uvicorn(monkeypatch) -> dict:
    """Replace ``uvicorn.run`` with a recorder and return the captured call."""
    captured: dict = {}

    def fake_run(served_app, **kwargs) -> None:
        captured["app"] = served_app
        captured["kwargs"] = kwargs

    monkeypatch.setattr(main_module.uvicorn, "run", fake_run)
    return captured


def test_main_passes_configured_host_and_port_to_uvicorn(monkeypatch):
    captured = _capture_uvicorn(monkeypatch)
    settings = Settings(_env_file=None, api_host="0.0.0.0", api_port=9443)

    main_module.main(settings)

    assert captured["kwargs"]["host"] == "0.0.0.0"
    assert captured["kwargs"]["port"] == 9443


def test_main_serves_the_module_level_app(monkeypatch):
    """The ASGI export and the served application must be the same object."""
    captured = _capture_uvicorn(monkeypatch)

    main_module.main(Settings(_env_file=None))

    assert captured["app"] is main_module.app


def test_main_defaults_to_the_settings_the_app_was_wired_with(monkeypatch):
    captured = _capture_uvicorn(monkeypatch)
    wired = main_module.app.state.settings

    main_module.main()

    assert captured["kwargs"]["host"] == wired.api_host
    assert captured["kwargs"]["port"] == wired.api_port


def test_main_translates_log_level_to_the_form_uvicorn_expects(monkeypatch):
    """Uvicorn expects lowercase level names; LearnFlow stores uppercase."""
    captured = _capture_uvicorn(monkeypatch)
    settings = Settings(_env_file=None, app_log_level=LogLevel.warning)

    main_module.main(settings)

    assert captured["kwargs"]["log_level"] == "warning"


def test_main_does_not_mutate_the_wired_settings(monkeypatch):
    captured = _capture_uvicorn(monkeypatch)
    before = main_module.app.state.settings

    main_module.main(Settings(_env_file=None, app_env=AppEnv.test, api_port=9001))

    assert main_module.app.state.settings is before
    assert captured["kwargs"]["port"] == 9001
