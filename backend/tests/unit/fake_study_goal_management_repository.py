"""An in-memory stand-in for the study-goal management repository port.

The curriculum reference data a goal binds to is supplied to the constructor,
because the study-goal endpoints only ever read it.

The stored-goal invariant is asserted on write, mirroring the database `CHECK`:
a fake that accepted a goal aiming at nothing would let a use case test pass on
a shape PostgreSQL would refuse. The availability writes assert the same way,
mirroring the unique `(study_goal_id, day_of_week)` key and the day and minute
`CHECK`s, so a use case test cannot pass on a week PostgreSQL would refuse.

Availability slots are returned in insertion order, not week order. The port
promises no order, and a fake that helpfully sorted them would hide a use case
that forgot to.
"""

import uuid
from collections.abc import Sequence

from app.application.dto.availability import MINUTES_IN_A_DAY, WEEKDAYS
from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
)
from app.application.ports.study_goal_management_repository import AvailabilitySlotRecord
from app.application.ports.study_goal_repository import StudyGoalRecord

ACTIVE_STATUS = "active"


class FakeStudyGoalManagementRepository:
    """Stores goals and their availability in lists, over fixed reference data."""

    def __init__(
        self,
        *,
        programs: Sequence[LearningProgramRecord] = (),
        versions: Sequence[CurriculumVersionRecord] = (),
        goals: Sequence[StudyGoalRecord] = (),
        availability: Sequence[AvailabilitySlotRecord] = (),
    ) -> None:
        self.programs = tuple(programs)
        self.versions = tuple(versions)
        self.goals: list[StudyGoalRecord] = list(goals)
        self.availability: list[AvailabilitySlotRecord] = list(availability)

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

    def list_availability_slots(
        self, study_goal_ids: Sequence[uuid.UUID]
    ) -> tuple[AvailabilitySlotRecord, ...]:
        wanted = set(study_goal_ids)
        return tuple(record for record in self.availability if record.study_goal_id in wanted)

    def add_availability_slot(self, record: AvailabilitySlotRecord) -> None:
        _require_a_storable_slot(record)
        if any(
            stored.study_goal_id == record.study_goal_id
            and stored.day_of_week == record.day_of_week
            for stored in self.availability
        ):
            raise AssertionError(
                f"{record.day_of_week} is already stored for study goal {record.study_goal_id}"
            )
        self.availability.append(record)

    def update_availability_slot(self, record: AvailabilitySlotRecord) -> None:
        _require_a_storable_slot(record)
        for index, stored in enumerate(self.availability):
            if stored.id == record.id:
                self.availability[index] = record
                return
        raise AssertionError(f"availability slot {record.id} is not stored")

    def delete_availability_slot(self, availability_slot_id: uuid.UUID) -> None:
        for index, stored in enumerate(self.availability):
            if stored.id == availability_slot_id:
                del self.availability[index]
                return
        raise AssertionError(f"availability slot {availability_slot_id} is not stored")


def _require_a_target(record: StudyGoalRecord) -> None:
    if record.target_date is None and record.examination_schedule_id is None:
        raise AssertionError("a study goal must aim at a date or an examination")


def _require_a_storable_slot(record: AvailabilitySlotRecord) -> None:
    if record.day_of_week not in WEEKDAYS:
        raise AssertionError(f"{record.day_of_week!r} is not a day of the week")
    if not 0 <= record.available_minutes <= MINUTES_IN_A_DAY:
        raise AssertionError(
            f"available minutes must be between 0 and {MINUTES_IN_A_DAY}, "
            f"not {record.available_minutes}"
        )
