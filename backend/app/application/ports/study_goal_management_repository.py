"""The persistence port the study-goal endpoints work through.

`StudyGoalRepository` already serves the `scripts.set_study_goal` command. This
is a second port rather than a widening of that one, because the two address the
same rows through different keys: a command resolves a learning program by the
code a human typed, while GOAL-001 to GOAL-004 resolve one by the identifier a
client read from CUR-001. A port carrying both would oblige every caller to be
trusted not to use the half that is wrong for it.

It reads the curriculum reference data a goal points at but never the examination
schedule: that is reference data of its own, reached through
`ExaminationScheduleRepository`, so the rule deciding which periods form the
examination window stays in one place.

Records are reused rather than redeclared, as elsewhere in this package. Ordering
of a page is fixed here, on `list_study_goals`, for the reason
`curriculum_repository` records: a page cannot be ordered after it has been
sliced.
"""

import uuid
from typing import Protocol

from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
)
from app.application.ports.study_goal_repository import StudyGoalRecord


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
