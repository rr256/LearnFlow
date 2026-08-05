"""An in-memory stand-in for the study-goal management repository port.

The curriculum reference data a goal binds to is supplied to the constructor,
because the study-goal endpoints only ever read it.

The stored-goal invariant is asserted on write, mirroring the database `CHECK`:
a fake that accepted a goal aiming at nothing would let a use case test pass on
a shape PostgreSQL would refuse.
"""

import uuid
from collections.abc import Sequence

from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
)
from app.application.ports.study_goal_repository import StudyGoalRecord

ACTIVE_STATUS = "active"


class FakeStudyGoalManagementRepository:
    """Stores goals in a list, over fixed curriculum reference data."""

    def __init__(
        self,
        *,
        programs: Sequence[LearningProgramRecord] = (),
        versions: Sequence[CurriculumVersionRecord] = (),
        goals: Sequence[StudyGoalRecord] = (),
    ) -> None:
        self.programs = tuple(programs)
        self.versions = tuple(versions)
        self.goals: list[StudyGoalRecord] = list(goals)

    def find_learning_program(self, learning_program_id: uuid.UUID) -> LearningProgramRecord | None:
        return next((record for record in self.programs if record.id == learning_program_id), None)

    def find_active_curriculum_version(
        self, learning_program_id: uuid.UUID
    ) -> CurriculumVersionRecord | None:
        return next(
            (
                record
                for record in self.versions
                if record.learning_program_id == learning_program_id
                and record.status == ACTIVE_STATUS
            ),
            None,
        )

    def find_curriculum_version(
        self, curriculum_version_id: uuid.UUID
    ) -> CurriculumVersionRecord | None:
        return next(
            (record for record in self.versions if record.id == curriculum_version_id), None
        )

    def count_study_goals(self, learner_id: uuid.UUID) -> int:
        return len([record for record in self.goals if record.learner_id == learner_id])

    def list_study_goals(
        self, *, learner_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[StudyGoalRecord, ...]:
        owned = [record for record in self.goals if record.learner_id == learner_id]
        return tuple(owned[offset : offset + limit])

    def find_study_goal(self, study_goal_id: uuid.UUID) -> StudyGoalRecord | None:
        return next((record for record in self.goals if record.id == study_goal_id), None)

    def find_active_study_goal(
        self, *, learner_id: uuid.UUID, learning_program_id: uuid.UUID
    ) -> StudyGoalRecord | None:
        return next(
            (
                record
                for record in self.goals
                if record.learner_id == learner_id
                and record.learning_program_id == learning_program_id
                and record.status == ACTIVE_STATUS
            ),
            None,
        )

    def add_study_goal(self, record: StudyGoalRecord) -> None:
        _require_a_target(record)
        self.goals.append(record)

    def update_study_goal(self, record: StudyGoalRecord) -> None:
        _require_a_target(record)
        for index, stored in enumerate(self.goals):
            if stored.id == record.id:
                self.goals[index] = record
                return
        raise AssertionError(f"study goal {record.id} is not stored")


def _require_a_target(record: StudyGoalRecord) -> None:
    if record.target_date is None and record.examination_schedule_id is None:
        raise AssertionError("a study goal must aim at a date or an examination")
