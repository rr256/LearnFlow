"""FastAPI application factory.

The composition root builds the running application: it validates configuration,
constructs the database engine and session factory, registers routes and, as the
backend grows, will construct repositories and provider adapters. It performs
wiring only -- never learning business rules.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.composition.config import Settings, load_settings
from app.infrastructure.persistence.engine import create_database_engine, create_session_factory
from app.presentation.api.routes import health


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Release pooled database connections when the process shuts down."""
    try:
        yield
    finally:
        app.state.database_engine.dispose()


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
        lifespan=_lifespan,
    )
    app.state.settings = settings

    # Held on app.state rather than in a module global so each application
    # instance owns its own pool and tests can build independent applications.
    engine = create_database_engine(str(settings.database_url))
    app.state.database_engine = engine
    app.state.session_factory = create_session_factory(engine)

    app.include_router(health.router)
    return app
