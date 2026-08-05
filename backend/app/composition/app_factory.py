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
from app.composition.providers import (
    build_learner_profile_provider,
    build_read_curriculum_provider,
    build_read_examination_schedules_provider,
    build_study_goals_provider,
    build_topic_progress_provider,
)
from app.infrastructure.persistence.engine import create_database_engine, create_session_factory
from app.presentation.api.dependencies import (
    LEARNER_PROFILE_PROVIDER,
    READ_CURRICULUM_PROVIDER,
    READ_EXAMINATION_SCHEDULES_PROVIDER,
    STUDY_GOALS_PROVIDER,
    TOPIC_PROGRESS_PROVIDER,
)
from app.presentation.api.errors import register_error_handlers
from app.presentation.api.routes import (
    curriculum,
    examination_schedules,
    health,
    learner,
    progress,
    study_goals,
)


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
    session_factory = create_session_factory(engine)
    app.state.session_factory = session_factory

    # The presentation layer asks for use cases, not repositories. Installing
    # the providers here keeps the choice of implementation in the only layer
    # permitted to make it. The learner-owned providers also own the
    # transaction, so no route has to remember to commit.
    setattr(app.state, READ_CURRICULUM_PROVIDER, build_read_curriculum_provider(session_factory))
    setattr(
        app.state,
        READ_EXAMINATION_SCHEDULES_PROVIDER,
        build_read_examination_schedules_provider(session_factory),
    )
    setattr(
        app.state,
        LEARNER_PROFILE_PROVIDER,
        build_learner_profile_provider(
            session_factory, default_timezone=settings.app_default_timezone
        ),
    )
    setattr(app.state, STUDY_GOALS_PROVIDER, build_study_goals_provider(session_factory))
    setattr(app.state, TOPIC_PROGRESS_PROVIDER, build_topic_progress_provider(session_factory))

    # Registered before the routers so every failure -- including a 404 for a
    # path no router claims -- is reported in the documented error envelope.
    register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(curriculum.router)
    app.include_router(examination_schedules.router)
    app.include_router(learner.router)
    app.include_router(study_goals.router)
    app.include_router(progress.router)
    return app
