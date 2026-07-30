"""FastAPI application factory.

The composition root builds the running application: it validates configuration,
registers routes and, as the backend grows, will construct repositories and
provider adapters. It performs wiring only -- never learning business rules.
"""

from fastapi import FastAPI

from app.composition.config import Settings, load_settings
from app.presentation.api.routes import health


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and wire a LearnFlow FastAPI application instance.

    Args:
        settings: Validated configuration. When omitted, it is loaded from the
            environment and any local ``.env`` file. Passing settings explicitly
            lets tests exercise wiring without touching the process environment.

    Raises:
        pydantic.ValidationError: If configuration is invalid. This is raised
            before the application object exists, so the process fails fast.
    """
    settings = settings or load_settings()

    app = FastAPI(
        title="LearnFlow API",
        version="0.1.0",
    )
    app.state.settings = settings
    app.include_router(health.router)
    return app
