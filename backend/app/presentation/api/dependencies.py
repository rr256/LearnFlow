"""Request-scoped dependencies for the API layer.

A route needs a use case, not a database. The composition root installs a
provider on the application state during startup, and each dependency below
opens one for the duration of a request and closes it afterwards.

Nothing here imports SQLAlchemy, a repository implementation, or configuration.
Which implementation fulfils a port is the composition root's decision alone
(docs/architecture/dependency-rules.md), so this module never learns what is
behind the provider it calls.

A provider that writes commits when the route returns without raising, and rolls
back otherwise. That decision belongs to the provider, not to a route: a route
that had to remember to commit is a route that will one day report success on
work that was discarded.
"""

from collections.abc import Iterator

from fastapi import Request

from app.application.use_cases.manage_learner_profile import ManageLearnerProfile
from app.application.use_cases.manage_study_goals import ManageStudyGoals
from app.application.use_cases.manage_study_plans import ManageStudyPlans
from app.application.use_cases.manage_topic_progress import ManageTopicProgress
from app.application.use_cases.read_curriculum import ReadCurriculum
from app.application.use_cases.read_examination_schedules import ReadExaminationSchedules

# The attributes the composition root installs on ``app.state``. Named once here
# so the two layers cannot drift apart over a typo.
READ_CURRICULUM_PROVIDER = "read_curriculum_provider"
READ_EXAMINATION_SCHEDULES_PROVIDER = "read_examination_schedules_provider"
LEARNER_PROFILE_PROVIDER = "learner_profile_provider"
STUDY_GOALS_PROVIDER = "study_goals_provider"
STUDY_PLANS_PROVIDER = "study_plans_provider"
TOPIC_PROGRESS_PROVIDER = "topic_progress_provider"


def provide_read_curriculum(request: Request) -> Iterator[ReadCurriculum]:
    """Yield a curriculum reader bound to this request's unit of work.

    The provider is a context manager, so the unit of work it opened is released
    once the response has been produced, including when the route raised.
    """
    provider = getattr(request.app.state, READ_CURRICULUM_PROVIDER)
    with provider() as use_case:
        yield use_case


def provide_read_examination_schedules(request: Request) -> Iterator[ReadExaminationSchedules]:
    """Yield an examination schedule reader bound to this request's unit of work."""
    provider = getattr(request.app.state, READ_EXAMINATION_SCHEDULES_PROVIDER)
    with provider() as use_case:
        yield use_case


def provide_learner_profile(request: Request) -> Iterator[ManageLearnerProfile]:
    """Yield the learner profile use case bound to this request's unit of work."""
    provider = getattr(request.app.state, LEARNER_PROFILE_PROVIDER)
    with provider() as use_case:
        yield use_case


def provide_study_goals(request: Request) -> Iterator[ManageStudyGoals]:
    """Yield the study-goal use case bound to this request's unit of work."""
    provider = getattr(request.app.state, STUDY_GOALS_PROVIDER)
    with provider() as use_case:
        yield use_case


def provide_study_plans(request: Request) -> Iterator[ManageStudyPlans]:
    """Yield the study-plan use case bound to this request's unit of work."""
    provider = getattr(request.app.state, STUDY_PLANS_PROVIDER)
    with provider() as use_case:
        yield use_case


def provide_topic_progress(request: Request) -> Iterator[ManageTopicProgress]:
    """Yield the topic-progress use case bound to this request's unit of work."""
    provider = getattr(request.app.state, TOPIC_PROGRESS_PROVIDER)
    with provider() as use_case:
        yield use_case
