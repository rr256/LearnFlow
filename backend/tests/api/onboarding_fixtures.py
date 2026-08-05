"""Fixtures for the learner onboarding API tests (LRN, GOAL, EXM).

The application is built through the real factory and the real use cases; only
the repositories are replaced. An API test therefore exercises routing,
validation, response mapping, and error mapping over the same code the running
backend uses, without needing PostgreSQL. The database counterpart is
tests/integration/test_learner_onboarding_api.py.

The providers installed here mirror the composition root's: one unit of work per
request. They hold no session, so nothing here needs to commit.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
)
from app.application.use_cases.manage_learner_profile import ManageLearnerProfile
from app.application.use_cases.manage_study_goals import ManageStudyGoals
from app.application.use_cases.read_examination_schedules import ReadExaminationSchedules
from app.presentation.api.dependencies import (
    LEARNER_PROFILE_PROVIDER,
    READ_EXAMINATION_SCHEDULES_PROVIDER,
    STUDY_GOALS_PROVIDER,
)
from tests.unit.fake_examination_schedule_repository import FakeExaminationScheduleRepository
from tests.unit.fake_learner_repository import FakeLearnerRepository
from tests.unit.fake_study_goal_management_repository import (
    FakeStudyGoalManagementRepository,
)
from tests.unit.schedule_fixtures import PROGRAM_ID, build_schedule, gate_2027_periods

DEFAULT_TIMEZONE = "Asia/Kolkata"

PROGRAM = LearningProgramRecord(
    id=PROGRAM_ID,
    code="gate-cse",
    name="GATE Computer Science and Information Technology",
    description="The first curated LearnFlow learning program.",
)
ACTIVE_VERSION = CurriculumVersionRecord(
    id=uuid.uuid4(),
    learning_program_id=PROGRAM_ID,
    version_label="2027",
    status="active",
    source_reference="https://example.test/syllabus",
    published_at=datetime(2026, 7, 31, 12, 0, tzinfo=UTC),
)


class Onboarding:
    """The stores the onboarding endpoints read and write, shared across a request."""

    def __init__(self) -> None:
        self.schedule = build_schedule()
        self.learners = FakeLearnerRepository()
        self.goals = FakeStudyGoalManagementRepository(
            programs=[PROGRAM], versions=[ACTIVE_VERSION]
        )
        self.schedules = FakeExaminationScheduleRepository(
            schedules=[self.schedule], periods=gate_2027_periods(self.schedule.id)
        )


def install_onboarding(app: FastAPI, onboarding: Onboarding) -> None:
    """Point the profile, goal, and schedule providers at one set of fakes."""

    @contextmanager
    def provide_profile() -> Iterator[ManageLearnerProfile]:
        yield ManageLearnerProfile(onboarding.learners, default_timezone=DEFAULT_TIMEZONE)

    @contextmanager
    def provide_goals() -> Iterator[ManageStudyGoals]:
        yield ManageStudyGoals(
            learners=onboarding.learners,
            goals=onboarding.goals,
            schedules=onboarding.schedules,
        )

    @contextmanager
    def provide_schedules() -> Iterator[ReadExaminationSchedules]:
        yield ReadExaminationSchedules(onboarding.schedules)

    setattr(app.state, LEARNER_PROFILE_PROVIDER, provide_profile)
    setattr(app.state, STUDY_GOALS_PROVIDER, provide_goals)
    setattr(app.state, READ_EXAMINATION_SCHEDULES_PROVIDER, provide_schedules)
