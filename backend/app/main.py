"""Application entry point.

Two supported ways to run the backend:

- ``python -m app.main`` -- serves the app on the configured ``API_HOST`` and
  ``API_PORT``. This is the path that honours LearnFlow configuration.
- ``python -m uvicorn app.main:app`` -- the ASGI import string, used by tests,
  reload workflows, and container process managers. Host and port then come from
  uvicorn's own arguments, not from LearnFlow settings.

The module-level ``app`` export is required by the second form and by ASGI tooling.
"""

import uvicorn
from fastapi import FastAPI

from app.composition.app_factory import create_app
from app.composition.config import Settings

app: FastAPI = create_app()


def main(settings: Settings | None = None) -> None:
    """Serve the application on the configured host and port.

    Args:
        settings: Configuration to serve with. Defaults to the settings the
            module-level ``app`` was wired with, so the server binds to exactly
            what the application was configured with and settings load once.
    """
    settings = settings or app.state.settings
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.app_log_level.value.lower(),
    )


if __name__ == "__main__":
    main()
