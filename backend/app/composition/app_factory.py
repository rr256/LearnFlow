"""FastAPI application factory.

The composition root builds the running application: it validates configuration,
constructs the database engine and session factory, registers routes and, as the
backend grows, will construct repositories and provider adapters. It performs
wiring only -- never learning business rules.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.application.ports.ai_provider import AIProvider
from app.application.ports.resource_file_storage import ResourceFileStorage
from app.composition.config import (
    AIProviderName,
    ResourceStorageProviderName,
    Settings,
    load_settings,
)
from app.composition.providers import (
    build_checkpoint_quizzes_provider,
    build_learner_profile_provider,
    build_practice_questions_provider,
    build_read_curriculum_provider,
    build_read_examination_schedules_provider,
    build_resource_files_provider,
    build_resource_notes_provider,
    build_resources_provider,
    build_revisions_provider,
    build_study_answer_provider,
    build_study_goals_provider,
    build_study_plans_provider,
    build_topic_note_retrieval_provider,
    build_topic_progress_provider,
)
from app.infrastructure.persistence.engine import create_database_engine, create_session_factory
from app.infrastructure.providers.ollama_ai_provider import OllamaAIProvider
from app.infrastructure.storage.local_file_storage import (
    LocalResourceFileStorage,
    PyPdfDocumentInspector,
)
from app.presentation.api.dependencies import (
    CHECKPOINT_QUIZZES_PROVIDER,
    LEARNER_PROFILE_PROVIDER,
    PRACTICE_QUESTIONS_PROVIDER,
    READ_CURRICULUM_PROVIDER,
    READ_EXAMINATION_SCHEDULES_PROVIDER,
    RESOURCE_FILES_PROVIDER,
    RESOURCE_NOTES_PROVIDER,
    RESOURCES_PROVIDER,
    REVISIONS_PROVIDER,
    STUDY_ANSWER_PROVIDER,
    STUDY_GOALS_PROVIDER,
    STUDY_PLANS_PROVIDER,
    TOPIC_NOTE_RETRIEVAL_PROVIDER,
    TOPIC_PROGRESS_PROVIDER,
)
from app.presentation.api.errors import register_error_handlers
from app.presentation.api.routes import (
    checkpoint_quizzes,
    curriculum,
    examination_schedules,
    health,
    learner,
    mentor,
    note_search,
    plan_items,
    practice_questions,
    progress,
    quiz_attempts,
    resource_files,
    resource_notes,
    resources,
    revisions,
    study_goals,
    study_plans,
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
    setattr(app.state, STUDY_PLANS_PROVIDER, build_study_plans_provider(session_factory))
    setattr(app.state, REVISIONS_PROVIDER, build_revisions_provider(session_factory))
    # Built once and shared: the stored-file use case writes and reads bytes
    # through it, and RES-005 unlinks them through the same adapter. It holds a
    # directory and no per-request state.
    file_storage = _select_file_storage(settings)
    setattr(
        app.state,
        RESOURCES_PROVIDER,
        build_resources_provider(session_factory, storage=file_storage),
    )
    setattr(app.state, RESOURCE_NOTES_PROVIDER, build_resource_notes_provider(session_factory))
    setattr(
        app.state,
        TOPIC_NOTE_RETRIEVAL_PROVIDER,
        build_topic_note_retrieval_provider(session_factory),
    )
    setattr(
        app.state,
        RESOURCE_FILES_PROVIDER,
        build_resource_files_provider(
            session_factory,
            storage=file_storage,
            inspector=PyPdfDocumentInspector(),
        ),
    )
    setattr(
        app.state,
        STUDY_ANSWER_PROVIDER,
        build_study_answer_provider(session_factory, ai_provider=_select_ai_provider(settings)),
    )
    setattr(app.state, TOPIC_PROGRESS_PROVIDER, build_topic_progress_provider(session_factory))
    setattr(
        app.state,
        PRACTICE_QUESTIONS_PROVIDER,
        build_practice_questions_provider(session_factory),
    )
    setattr(
        app.state,
        CHECKPOINT_QUIZZES_PROVIDER,
        build_checkpoint_quizzes_provider(session_factory),
    )

    # Registered before the routers so every failure -- including a 404 for a
    # path no router claims -- is reported in the documented error envelope.
    register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(curriculum.router)
    app.include_router(examination_schedules.router)
    app.include_router(learner.router)
    app.include_router(study_goals.router)
    app.include_router(study_plans.router)
    app.include_router(study_plans.goal_router)
    app.include_router(plan_items.router)
    app.include_router(progress.router)
    app.include_router(revisions.router)
    app.include_router(resources.router)
    # Registered *before* `resource_notes`, whose `/resource-notes/{note_id}`
    # would otherwise capture `/resource-notes/search`: a path parameter matches
    # any segment and is only validated as a UUID afterwards, so the collision
    # would surface as a 422 rather than as a route that never ran.
    app.include_router(mentor.router)
    app.include_router(resource_files.router)
    app.include_router(note_search.router)
    app.include_router(resource_notes.router)
    app.include_router(practice_questions.router)
    app.include_router(checkpoint_quizzes.router)
    app.include_router(quiz_attempts.router)
    return app


def _select_ai_provider(settings: Settings) -> AIProvider:
    """The adapter that fulfils the `AIProvider` port for this process.

    **The only place an AI provider is chosen.** `AI_PROVIDER` names a capability
    and this function turns that name into one object; nothing else in the
    backend imports an adapter, so what a learner's passages are sent to is
    decided here and read in one place.

    Built once at startup rather than per request: the adapter holds a URL, a
    model name, and a timeout, so there is nothing request-scoped in it.

    The match is exhaustive over `AIProviderName`, so adding a member without an
    adapter fails the type check rather than at the first question a learner asks.
    """
    match settings.ai_provider:
        case AIProviderName.ollama:
            return OllamaAIProvider(
                base_url=str(settings.ollama_base_url),
                model=settings.ollama_chat_model,
                timeout_seconds=settings.ai_request_timeout_seconds,
            )


def _select_file_storage(settings: Settings) -> ResourceFileStorage:
    """Where a learner's uploaded file bytes are kept, for this process.

    **The only place a storage adapter is chosen**, and the only place the
    storage path is read. `RESOURCE_STORAGE_PROVIDER` names a capability and this
    turns it into one object; nothing else in the backend imports an adapter, so
    where a learner's files land is decided here and read in one place.

    The match is exhaustive over `ResourceStorageProviderName`, so adding a
    member without an adapter fails the type check rather than at the first
    upload a learner attempts.
    """
    match settings.resource_storage_provider:
        case ResourceStorageProviderName.local:
            return LocalResourceFileStorage(root=settings.resource_storage_path)
