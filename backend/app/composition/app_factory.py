"""FastAPI application factory.

The composition root builds the running application: it registers routes and, as
the backend grows, will construct configuration, repositories, and provider
adapters. It performs wiring only -- never learning business rules.
"""

from fastapi import FastAPI

from app.presentation.api.routes import health


def create_app() -> FastAPI:
    """Create and wire a LearnFlow FastAPI application instance."""
    app = FastAPI(
        title="LearnFlow API",
        version="0.1.0",
    )
    app.include_router(health.router)
    return app
