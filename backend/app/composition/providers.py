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

from app.application.ports.clock import Clock
from app.application.use_cases.manage_checkpoint_quizzes import ManageCheckpointQuizzes
from app.application.use_cases.manage_learner_profile import ManageLearnerProfile
from app.application.use_cases.manage_practice_questions import ManagePracticeQuestions
from app.application.use_cases.manage_resource_notes import ManageResourceNotes
from app.application.use_cases.manage_resources import ManageResources
from app.application.use_cases.manage_revisions import ManageRevisions
from app.application.use_cases.manage_study_goals import ManageStudyGoals
from app.application.use_cases.manage_study_plans import ManageStudyPlans
from app.application.use_cases.manage_topic_progress import ManageTopicProgress
from app.application.use_cases.read_curriculum import ReadCurriculum
from app.application.use_cases.read_examination_schedules import ReadExaminationSchedules
from app.infrastructure.clock import SystemClock
from app.infrastructure.persistence.checkpoint_practice_repository import (
    SqlAlchemyCheckpointPracticeRepository,
)
from app.infrastructure.persistence.curriculum_repository import SqlAlchemyCurriculumRepository
from app.infrastructure.persistence.examination_schedule_repository import (
    SqlAlchemyExaminationScheduleRepository,
)
from app.infrastructure.persistence.learner_repository import SqlAlchemyLearnerRepository
from app.infrastructure.persistence.resource_note_repository import (
    SqlAlchemyResourceNoteRepository,
)
from app.infrastructure.persistence.resource_repository import SqlAlchemyResourceRepository
from app.infrastructure.persistence.revision_repository import SqlAlchemyRevisionRepository
from app.infrastructure.persistence.study_goal_management_repository import (
    SqlAlchemyStudyGoalManagementRepository,
)
from app.infrastructure.persistence.study_plan_repository import SqlAlchemyStudyPlanRepository
from app.infrastructure.persistence.topic_progress_repository import (
    SqlAlchemyTopicProgressRepository,
)

ReadCurriculumProvider = Callable[[], AbstractContextManager[ReadCurriculum]]
ReadExaminationSchedulesProvider = Callable[[], AbstractContextManager[ReadExaminationSchedules]]
LearnerProfileProvider = Callable[[], AbstractContextManager[ManageLearnerProfile]]
StudyGoalsProvider = Callable[[], AbstractContextManager[ManageStudyGoals]]
StudyPlansProvider = Callable[[], AbstractContextManager[ManageStudyPlans]]
RevisionsProvider = Callable[[], AbstractContextManager[ManageRevisions]]
ResourcesProvider = Callable[[], AbstractContextManager[ManageResources]]
ResourceNotesProvider = Callable[[], AbstractContextManager[ManageResourceNotes]]
TopicProgressProvider = Callable[[], AbstractContextManager[ManageTopicProgress]]
PracticeQuestionsProvider = Callable[[], AbstractContextManager[ManagePracticeQuestions]]
CheckpointQuizzesProvider = Callable[[], AbstractContextManager[ManageCheckpointQuizzes]]


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


def build_study_plans_provider(
    session_factory: sessionmaker[Session], *, clock: Clock | None = None
) -> StudyPlansProvider:
    """Build the provider that hands the study-plan use case to one request.

    The planner reads through five repositories and writes through one, all bound
    to the same session, so a generation that supersedes an old plan and writes a
    new one is a single unit of work: a learner cannot end up with two active
    plans, or with none.

    Args:
        session_factory: The application's shared session factory.
        clock: Where "today" comes from. Defaults to the system clock; a caller
            supplies one to fix the date, which is what makes a generated plan's
            dates assertable.
    """
    reads_the_clock = clock or SystemClock()

    @contextmanager
    def provide() -> Iterator[ManageStudyPlans]:
        with session_factory() as session:
            try:
                yield ManageStudyPlans(
                    learners=SqlAlchemyLearnerRepository(session),
                    goals=SqlAlchemyStudyGoalManagementRepository(session),
                    schedules=SqlAlchemyExaminationScheduleRepository(session),
                    curriculum=SqlAlchemyCurriculumRepository(session),
                    progress=SqlAlchemyTopicProgressRepository(session),
                    plans=SqlAlchemyStudyPlanRepository(session),
                    clock=reads_the_clock,
                )
            except BaseException:
                session.rollback()
                raise
            session.commit()

    return provide


def build_revisions_provider(
    session_factory: sessionmaker[Session], *, clock: Clock | None = None
) -> RevisionsProvider:
    """Build the provider that hands the revision use case to one request.

    Reads and writes through one repository bound to one session, so a scheduling
    run that creates several revisions is a single unit of work: a learner cannot
    end up with half a round scheduled.

    Args:
        session_factory: The application's shared session factory.
        clock: Where "today" comes from, and where a completion's timestamp comes
            from. Defaults to the system clock; a caller supplies one to fix the
            date, which is what makes a revision's due date assertable.
    """
    reads_the_clock = clock or SystemClock()

    @contextmanager
    def provide() -> Iterator[ManageRevisions]:
        with session_factory() as session:
            try:
                yield ManageRevisions(
                    learners=SqlAlchemyLearnerRepository(session),
                    revisions=SqlAlchemyRevisionRepository(session),
                    clock=reads_the_clock,
                )
            except BaseException:
                session.rollback()
                raise
            session.commit()

    return provide


def build_resources_provider(
    session_factory: sessionmaker[Session],
) -> ResourcesProvider:
    """Build the provider that hands the learning-resource use case to one request.

    It writes, so it owns the transaction like the other learner-owned providers.
    Registering a resource and linking it to several topics is one unit of work:
    a learner cannot end up with material in the catalogue that covers none of
    the topics they chose, or with links to a resource that was never written.

    It reads no clock and no configuration. Nothing about a resource depends on
    the date, so there is no timezone to resolve and no `Clock` port to bind.
    """

    @contextmanager
    def provide() -> Iterator[ManageResources]:
        with session_factory() as session:
            try:
                yield ManageResources(
                    learners=SqlAlchemyLearnerRepository(session),
                    resources=SqlAlchemyResourceRepository(session),
                )
            except BaseException:
                session.rollback()
                raise
            session.commit()

    return provide


def build_resource_notes_provider(
    session_factory: sessionmaker[Session],
) -> ResourceNotesProvider:
    """Build the provider that hands the resource-note use case to one request.

    It writes, so it owns the transaction like the other learner-owned providers.

    It binds three repositories and **no provider**: learners, to resolve who is
    asking; resources, to check that the material is theirs and still in the
    catalogue; and notes. There is deliberately no AI provider, no embedding
    provider, and no retrieval provider here — a learner's note has no path out
    of this process, and adding one to this constructor is the visible decision
    that would change that (NFR-001).

    It reads no clock and no configuration. Nothing about a note depends on the
    date, so there is no timezone to resolve and no `Clock` port to bind.
    """

    @contextmanager
    def provide() -> Iterator[ManageResourceNotes]:
        with session_factory() as session:
            try:
                yield ManageResourceNotes(
                    learners=SqlAlchemyLearnerRepository(session),
                    resources=SqlAlchemyResourceRepository(session),
                    notes=SqlAlchemyResourceNoteRepository(session),
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


def build_practice_questions_provider(
    session_factory: sessionmaker[Session], *, clock: Clock | None = None
) -> PracticeQuestionsProvider:
    """Build the provider that hands the practice-question use case to one request.

    It writes, so it owns the transaction like the other learner-owned providers:
    a question and the topics it covers are one unit of work, so a learner cannot
    end up with a question no quiz could ever ask.

    It reads the clock because a question's `written_at` is what a quiz is ordered
    by, and a caller able to supply that instant could reorder a quiz.

    Args:
        session_factory: The application's shared session factory.
        clock: Where "now" comes from. Defaults to the system clock; a caller
            supplies one to fix the instant, which is what makes a quiz's order
            assertable.
    """
    reads_the_clock = clock or SystemClock()

    @contextmanager
    def provide() -> Iterator[ManagePracticeQuestions]:
        with session_factory() as session:
            try:
                yield ManagePracticeQuestions(
                    learners=SqlAlchemyLearnerRepository(session),
                    practice=SqlAlchemyCheckpointPracticeRepository(session),
                    clock=reads_the_clock,
                )
            except BaseException:
                session.rollback()
                raise
            session.commit()

    return provide


def build_checkpoint_quizzes_provider(
    session_factory: sessionmaker[Session], *, clock: Clock | None = None
) -> CheckpointQuizzesProvider:
    """Build the provider that hands the checkpoint-quiz use case to one request.

    It writes, so it owns the transaction. Assembling a quiz writes the quiz, the
    topics it covers, and the questions it asks, and marking an attempt writes the
    attempt and every answer: each is one unit of work, so a learner cannot end up
    with a quiz that asks nothing or a result that marked half its questions.

    It reads the clock because an attempt's `started_at`, `submitted_at`, and
    `evaluated_at` all come from the server rather than from a caller — the rule
    ADR-021 fixed for `plan_items.completed_at`.

    Args:
        session_factory: The application's shared session factory.
        clock: Where "now" comes from. Defaults to the system clock; a caller
            supplies one to fix the instant an attempt was marked.
    """
    reads_the_clock = clock or SystemClock()

    @contextmanager
    def provide() -> Iterator[ManageCheckpointQuizzes]:
        with session_factory() as session:
            try:
                yield ManageCheckpointQuizzes(
                    learners=SqlAlchemyLearnerRepository(session),
                    practice=SqlAlchemyCheckpointPracticeRepository(session),
                    clock=reads_the_clock,
                )
            except BaseException:
                session.rollback()
                raise
            session.commit()

    return provide
