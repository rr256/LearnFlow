"""An in-memory stand-in for the study goal repository port.

The reference data a goal points at -- the program, its active curriculum
version, the published schedule and its periods -- is supplied to the
constructor, because the goal use case only ever reads it.
"""

import uuid

from app.application.ports.examination_schedule_repository import (
    ExaminationPeriodRecord,
    ExaminationScheduleRecord,
)
from app.application.ports.study_goal_repository import (
    CurriculumVersionSummary,
    LearnerRecord,
    StudyGoalRecord,
)


class FakeStudyGoalRepository:
    """Stores learners and goals in dictionaries, over fixed reference data."""

    def __init__(
        self,
        *,
        learning_programs: dict[str, uuid.UUID] | None = None,
        active_versions: dict[uuid.UUID, CurriculumVersionSummary] | None = None,
        schedules: tuple[ExaminationScheduleRecord, ...] = (),
        periods: tuple[ExaminationPeriodRecord, ...] = (),
    ) -> None:
        self.learning_programs = dict(learning_programs or {})
        self.active_versions = dict(active_versions or {})
        self.schedules = schedules
        self.periods = periods
        self.learners: dict[uuid.UUID, LearnerRecord] = {}
        self.goals: dict[uuid.UUID, StudyGoalRecord] = {}

    def list_learners(self) -> tuple[LearnerRecord, ...]:
        return tuple(self.learners.values())

    def add_learner(self, record: LearnerRecord) -> None:
        self.learners[record.id] = record

    def find_learning_program_id(self, code: str) -> uuid.UUID | None:
        return self.learning_programs.get(code)

    def find_active_curriculum_version(
        self, learning_program_id: uuid.UUID
    ) -> CurriculumVersionSummary | None:
        return self.active_versions.get(learning_program_id)

    def find_examination_schedule(
        self, *, learning_program_id: uuid.UUID, cycle_label: str
    ) -> ExaminationScheduleRecord | None:
        return next(
            (
                record
                for record in self.schedules
                if record.learning_program_id == learning_program_id
                and record.cycle_label == cycle_label
            ),
            None,
        )

    def list_examination_periods(
        self, examination_schedule_id: uuid.UUID
    ) -> tuple[ExaminationPeriodRecord, ...]:
        return tuple(
            sorted(
                (
                    record
                    for record in self.periods
                    if record.examination_schedule_id == examination_schedule_id
                ),
                key=lambda record: (record.starts_on, record.period_type),
            )
        )

    def find_active_study_goal(
        self, *, learner_id: uuid.UUID, learning_program_id: uuid.UUID
    ) -> StudyGoalRecord | None:
        return next(
            (
                record
                for record in self.goals.values()
                if record.learner_id == learner_id
                and record.learning_program_id == learning_program_id
                and record.status == "active"
            ),
            None,
        )

    def add_study_goal(self, record: StudyGoalRecord) -> None:
        if record.target_date is None and record.examination_schedule_id is None:
            raise AssertionError("a study goal must aim at a date or an examination")
        self.goals[record.id] = record

    def update_study_goal(self, record: StudyGoalRecord) -> None:
        if record.id not in self.goals:
            raise AssertionError(f"study goal {record.id} is not stored")
        if record.target_date is None and record.examination_schedule_id is None:
            raise AssertionError("a study goal must aim at a date or an examination")
        self.goals[record.id] = record
