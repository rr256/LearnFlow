"""The learner, goal, curriculum, and stores the planning tests share.

Shaped like the curated GATE CSE curriculum in the ways that matter to a plan: a
grouping topic that holds subtopics and cannot be planned, leaves that can, two
subjects in a stated order, and a published examination schedule sat over three
weekends.

These are test fixtures, not curriculum content: no GATE CSE syllabus data is
expressed here.

Shared by the use-case tests and the API tests, so both exercise the same shape
and a rule proved against one cannot quietly differ in the other.
"""

import uuid
from datetime import UTC, date, datetime

from app.application.dto.planning_preferences import PlanningPreferences
from app.application.dto.study_plan import PlanGenerationRequest
from app.application.dto.topic_progress import TopicProgressTopic
from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    SubjectRecord,
    TopicRecord,
)
from app.application.ports.study_goal_management_repository import AvailabilitySlotRecord
from app.application.ports.study_goal_repository import StudyGoalRecord
from app.application.use_cases.manage_study_plans import ManageStudyPlans
from tests.unit.fake_curriculum_repository import FakeCurriculumRepository
from tests.unit.fake_examination_schedule_repository import FakeExaminationScheduleRepository
from tests.unit.fake_learner_repository import FakeLearnerRepository, learner
from tests.unit.fake_study_goal_management_repository import FakeStudyGoalManagementRepository
from tests.unit.fake_study_plan_repository import FakeStudyPlanRepository
from tests.unit.fake_topic_progress_repository import FakeTopicProgressRepository
from tests.unit.schedule_fixtures import build_schedule, gate_2027_periods

# A Thursday, so a week built from it crosses a weekend and cannot pass by
# accidentally starting on the day the weekday list starts.
TODAY = date(2026, 8, 6)

DEFAULT_INSTANT = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)
"""Mid-morning UTC on `TODAY`, so no timezone conversion moves the date."""


class FixedClock:
    """A clock that always reports the same instant."""

    def __init__(self, instant: datetime) -> None:
        self.instant = instant

    def now(self) -> datetime:
        return self.instant


class Planning:
    """A learner, a goal, a two-subject curriculum, and somewhere to put plans.

    The curriculum is shaped like the curated GATE CSE one: a grouping topic that
    holds subtopics and cannot be planned, and leaves that can.
    """

    def __init__(
        self,
        *,
        preferences: PlanningPreferences | None = None,
        availability: dict[str, int] | None = None,
        aims_at_examination: bool = True,
        target_date: date | None = None,
        timezone: str = "Asia/Kolkata",
        instant: datetime = DEFAULT_INSTANT,
    ) -> None:
        preferences = preferences or PlanningPreferences()
        self.learner = learner(timezone=timezone)
        self.program_id = uuid.uuid4()
        self.version = CurriculumVersionRecord(
            id=uuid.uuid4(),
            learning_program_id=self.program_id,
            version_label="2027",
            status="active",
            source_reference=None,
            published_at=None,
        )
        self.first_subject = SubjectRecord(
            id=uuid.uuid4(),
            curriculum_version_id=self.version.id,
            code="engineering-mathematics",
            name="Engineering Mathematics",
            description=None,
            position=1,
        )
        self.second_subject = SubjectRecord(
            id=uuid.uuid4(),
            curriculum_version_id=self.version.id,
            code="operating-systems",
            name="Operating Systems",
            description=None,
            position=2,
        )
        self.grouping = self._topic(self.first_subject.id, "Discrete Mathematics", 1, False)
        self.logic = self._topic(
            self.first_subject.id, "Propositional logic", 1, True, parent=self.grouping.id
        )
        self.sets = self._topic(
            self.first_subject.id, "Sets and relations", 2, True, parent=self.grouping.id
        )
        self.scheduling = self._topic(self.second_subject.id, "CPU scheduling", 1, True)

        self.schedule = build_schedule(learning_program_id=self.program_id)
        self.periods = gate_2027_periods(self.schedule.id)
        self.goal = StudyGoalRecord(
            id=uuid.uuid4(),
            learner_id=self.learner.id,
            learning_program_id=self.program_id,
            curriculum_version_id=self.version.id,
            examination_schedule_id=self.schedule.id if aims_at_examination else None,
            target_date=target_date,
            status="active",
            planning_preferences=preferences,
        )
        self.learners = FakeLearnerRepository((self.learner,))
        self.goals = FakeStudyGoalManagementRepository(
            versions=[self.version],
            goals=[self.goal],
            availability=[
                AvailabilitySlotRecord(
                    id=uuid.uuid4(),
                    study_goal_id=self.goal.id,
                    day_of_week=day,
                    available_minutes=minutes,
                )
                for day, minutes in (availability or {}).items()
            ],
        )
        self.curriculum = FakeCurriculumRepository(
            versions=[self.version],
            subjects=[self.first_subject, self.second_subject],
            topics=[self.grouping, self.logic, self.sets, self.scheduling],
        )
        self.progress = FakeTopicProgressRepository(
            tuple(
                TopicProgressTopic(
                    id=record.id,
                    code=None,
                    name=record.name,
                    is_trackable=record.is_trackable,
                    subject_id=record.subject_id,
                    curriculum_version_id=self.version.id,
                )
                for record in (self.grouping, self.logic, self.sets, self.scheduling)
            )
        )
        self.plans = FakeStudyPlanRepository(
            subjects=[self.first_subject, self.second_subject],
            topics=[self.grouping, self.logic, self.sets, self.scheduling],
        )
        self.clock = FixedClock(instant)

    def _topic(
        self,
        subject_id: uuid.UUID,
        name: str,
        position: int,
        is_trackable: bool,
        parent: uuid.UUID | None = None,
    ) -> TopicRecord:
        return TopicRecord(
            id=uuid.uuid4(),
            subject_id=subject_id,
            parent_topic_id=parent,
            code=None,
            name=name,
            description=None,
            position=position,
            is_trackable=is_trackable,
        )

    def planner(self) -> ManageStudyPlans:
        return ManageStudyPlans(
            learners=self.learners,
            goals=self.goals,
            schedules=FakeExaminationScheduleRepository(
                schedules=[self.schedule], periods=self.periods
            ),
            curriculum=self.curriculum,
            progress=self.progress,
            plans=self.plans,
            clock=self.clock,
        )

    def generate(self):
        return self.planner().generate(PlanGenerationRequest(study_goal_id=self.goal.id))
