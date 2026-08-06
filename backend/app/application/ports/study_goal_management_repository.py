"""The persistence port the study-goal endpoints work through.

`StudyGoalRepository` already serves the `scripts.set_study_goal` command. This
is a second port rather than a widening of that one, because the two address the
same rows through different keys: a command resolves a learning program by the
code a human typed, while GOAL-001 to GOAL-005 resolve one by the identifier a
client read from CUR-001. A port carrying both would oblige every caller to be
trusted not to use the half that is wrong for it.

It reads the curriculum reference data a goal points at but never the examination
schedule: that is reference data of its own, reached through
`ExaminationScheduleRepository`, so the rule deciding which periods form the
examination window stays in one place.

Availability slots are read and written here rather than through a port of their
own. A slot has meaning only under the goal that owns it -- it is reached by a
nested path, it is returned inside a goal response, and every read of it is
scoped by a goal identifier -- so a separate port would divide one aggregate
between two interfaces and oblige a request to open two of them.

Records are reused rather than redeclared, as elsewhere in this package. Ordering
of a page is fixed here, on `list_study_goals`, for the reason
`curriculum_repository` records: a page cannot be ordered after it has been
sliced. Availability is the one exception: its order is a fixed week rather than
a query result, so the use case sorts it.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
)
from app.application.ports.study_goal_repository import StudyGoalRecord


@dataclass(frozen=True, slots=True)
class AvailabilitySlotRecord:
    """One stored day of a goal's weekly availability.

    Carries `id` where the application DTO does not, because saving a week
    rewrites the days it names in place: an unchanged day keeps its row, its
    identifier, and its `created_at` rather than being deleted and written again.
    No client ever sees the identifier.
    """

    id: uuid.UUID
    study_goal_id: uuid.UUID
    day_of_week: str
    available_minutes: int


class StudyGoalManagementRepository(Protocol):
    """Reads and writes the records the study-goal endpoints touch."""

    def find_learning_program(self, learning_program_id: uuid.UUID) -> LearningProgramRecord | None:
        """The program with this identifier, or None."""
        ...

    def find_active_curriculum_version(
        self, learning_program_id: uuid.UUID
    ) -> CurriculumVersionRecord | None:
        """The program's active curriculum version, or None.

        At most one can exist: a partial unique index enforces it (ADR-011).
        """
        ...

    def find_curriculum_version(
        self, curriculum_version_id: uuid.UUID
    ) -> CurriculumVersionRecord | None:
        """The curriculum version with this identifier, or None.

        A stored goal names the version it was created against, which may since
        have been retired. Reading it by identifier reports what the goal is
        actually bound to rather than what is active today.
        """
        ...

    def count_study_goals(self, learner_id: uuid.UUID) -> int:
        """How many goals this learner has, ignoring any page window."""
        ...

    def list_study_goals(
        self, *, learner_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[StudyGoalRecord, ...]:
        """One page of the learner's goals, newest first."""
        ...

    def find_study_goal(self, study_goal_id: uuid.UUID) -> StudyGoalRecord | None:
        """The goal with this identifier, or None.

        Ownership is deliberately not filtered here. Whether a goal belongs to
        the effective learner is a rule, so the use case decides it.
        """
        ...

    def find_active_study_goal(
        self, *, learner_id: uuid.UUID, learning_program_id: uuid.UUID
    ) -> StudyGoalRecord | None:
        """The learner's active goal for this program, or None.

        Goals that are paused, completed, or archived are history; a new goal for
        the same program does not conflict with them.
        """
        ...

    def add_study_goal(self, record: StudyGoalRecord) -> None:
        """Store a new study goal."""
        ...

    def update_study_goal(self, record: StudyGoalRecord) -> None:
        """Overwrite the stored goal identified by ``record.id``."""
        ...

    def list_availability_slots(
        self, study_goal_ids: Sequence[uuid.UUID]
    ) -> tuple[AvailabilitySlotRecord, ...]:
        """Every availability slot belonging to the goals named, in no order.

        Every identifier is asked for at once so returning a page of goals stays
        one query rather than one per goal. A goal with no availability stored
        contributes nothing to the result, which is how an unset week is
        reported.
        """
        ...

    def add_availability_slot(self, record: AvailabilitySlotRecord) -> None:
        """Store a new availability slot."""
        ...

    def update_availability_slot(self, record: AvailabilitySlotRecord) -> None:
        """Overwrite the stored slot identified by ``record.id``."""
        ...

    def delete_availability_slot(self, availability_slot_id: uuid.UUID) -> None:
        """Remove the stored slot with this identifier.

        This deletes learner-owned data, so only the use case serving GOAL-005
        calls it, and only for a day the learner's own replacement no longer
        names.
        """
        ...
