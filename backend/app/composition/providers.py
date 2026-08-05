"""Request-scoped provider construction.

Only the composition root decides which implementation fulfils an application
port, so the choice of a SQLAlchemy repository is made here and nowhere else
(docs/architecture/dependency-rules.md). The presentation layer receives a
callable that hands it a ready use case and never learns what is behind it.

Each call opens one unit of work and closes it when the caller is done. The read
providers never commit: closing the session ends the transaction it opened. The
writing providers commit when the block exits without an exception and roll back
otherwise, so a route cannot report success on work that was discarded, and a
route that raised cannot leave a half-written record behind.

Configuration is read here too, and only here. `APP_DEFAULT_TIMEZONE` reaches the
learner profile use case as an argument rather than as an environment lookup,
because application code must never read configuration itself.
"""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

from sqlalchemy.orm import Session, sessionmaker

from app.application.use_cases.manage_learner_profile import ManageLearnerProfile
from app.application.use_cases.manage_study_goals import ManageStudyGoals
from app.application.use_cases.manage_topic_progress import ManageTopicProgress
from app.application.use_cases.read_curriculum import ReadCurriculum
from app.application.use_cases.read_examination_schedules import ReadExaminationSchedules
from app.infrastructure.persistence.curriculum_repository import SqlAlchemyCurriculumRepository
from app.infrastructure.persistence.examination_schedule_repository import (
    SqlAlchemyExaminationScheduleRepository,
)
from app.infrastructure.persistence.learner_repository import SqlAlchemyLearnerRepository
from app.infrastructure.persistence.study_goal_management_repository import (
    SqlAlchemyStudyGoalManagementRepository,
)
from app.infrastructure.persistence.topic_progress_repository import (
    SqlAlchemyTopicProgressRepository,
)

ReadCurriculumProvider = Callable[[], AbstractContextManager[ReadCurriculum]]
ReadExaminationSchedulesProvider = Callable[[], AbstractContextManager[ReadExaminationSchedules]]
LearnerProfileProvider = Callable[[], AbstractContextManager[ManageLearnerProfile]]
StudyGoalsProvider = Callable[[], AbstractContextManager[ManageStudyGoals]]
TopicProgressProvider = Callable[[], AbstractContextManager[ManageTopicProgress]]


def build_read_curriculum_provider(
    session_factory: sessionmaker[Session],
) -> ReadCurriculumProvider:
    """Build the provider that hands a curriculum reader to one request.

    Args:
        session_factory: The application's shared session factory. It is bound
            once at startup, so a request pays for a pooled connection rather
            than for building an engine.
    """

    @contextmanager
    def provide() -> Iterator[ReadCurriculum]:
        with session_factory() as session:
            yield ReadCurriculum(SqlAlchemyCurriculumRepository(session))

    return provide


def build_read_examination_schedules_provider(
    session_factory: sessionmaker[Session],
) -> ReadExaminationSchedulesProvider:
    """Build the provider that hands an examination schedule reader to one request."""

    @contextmanager
    def provide() -> Iterator[ReadExaminationSchedules]:
        with session_factory() as session:
            yield ReadExaminationSchedules(SqlAlchemyExaminationScheduleRepository(session))

    return provide


def build_learner_profile_provider(
    session_factory: sessionmaker[Session], *, default_timezone: str
) -> LearnerProfileProvider:
    """Build the provider that hands the learner profile use case to one request.

    Args:
        session_factory: The application's shared session factory.
        default_timezone: `APP_DEFAULT_TIMEZONE`, validated at startup as a real
            IANA zone. It is the timezone a learner record is created with when
            the request names none.
    """

    @contextmanager
    def provide() -> Iterator[ManageLearnerProfile]:
        with session_factory() as session:
            try:
                yield ManageLearnerProfile(
                    SqlAlchemyLearnerRepository(session), default_timezone=default_timezone
                )
            except BaseException:
                session.rollback()
                raise
            session.commit()

    return provide


def build_study_goals_provider(
    session_factory: sessionmaker[Session],
) -> StudyGoalsProvider:
    """Build the provider that hands the study-goal use case to one request."""

    @contextmanager
    def provide() -> Iterator[ManageStudyGoals]:
        with session_factory() as session:
            try:
                yield ManageStudyGoals(
                    learners=SqlAlchemyLearnerRepository(session),
                    goals=SqlAlchemyStudyGoalManagementRepository(session),
                    schedules=SqlAlchemyExaminationScheduleRepository(session),
                )
            except BaseException:
                session.rollback()
                raise
            session.commit()

    return provide


def build_topic_progress_provider(
    session_factory: sessionmaker[Session],
) -> TopicProgressProvider:
    """Build the provider that hands the topic-progress use case to one request.

    It writes, so it owns the transaction like the other learner-owned
    providers: a route that reported a saved stage over a rolled-back session
    would tell a learner their work was recorded when it was not.
    """

    @contextmanager
    def provide() -> Iterator[ManageTopicProgress]:
        with session_factory() as session:
            try:
                yield ManageTopicProgress(
                    learners=SqlAlchemyLearnerRepository(session),
                    progress=SqlAlchemyTopicProgressRepository(session),
                )
            except BaseException:
                session.rollback()
                raise
            session.commit()

    return provide
