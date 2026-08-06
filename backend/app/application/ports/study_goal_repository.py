"""The persistence port the study goal use case works through.

It reads three things it does not own -- the learning program, its active
curriculum version, and the published examination schedule -- and reads and
writes the two it does: the learner and the learner's study goal.

Reading the examination schedule here rather than deriving anything from it
keeps the rule that decides *which* periods form the examination window in the
use case, where it can be tested without a database.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.application.dto.planning_preferences import PlanningPreferences
from app.application.ports.examination_schedule_repository import (
    ExaminationPeriodRecord,
    ExaminationScheduleRecord,
)


@dataclass(frozen=True, slots=True)
class LearnerRecord:
    """A stored learner identity and its local preferences."""

    id: uuid.UUID
    display_name: str | None
    timezone: str


@dataclass(frozen=True, slots=True)
class CurriculumVersionSummary:
    """Just enough of a curriculum version to bind a goal to it and name it back."""

    id: uuid.UUID
    version_label: str


@dataclass(frozen=True, slots=True)
class StudyGoalRecord:
    """A stored study goal.

    ``target_date`` and ``examination_schedule_id`` are both nullable, and a
    database CHECK requires at least one of them: a goal aims at a published
    examination cycle, at a plain completion date, or at both -- never at
    nothing.

    ``planning_preferences`` is always present and may be empty, never ``None``,
    so no reader needs a branch for a goal stored before preferences existed. It
    is part of the record rather than read separately because the columns live on
    this row -- which also means a caller comparing a desired record with the
    stored one detects a changed preference for free, and a caller that means to
    leave preferences alone must copy them across deliberately.
    """

    id: uuid.UUID
    learner_id: uuid.UUID
    learning_program_id: uuid.UUID
    curriculum_version_id: uuid.UUID
    examination_schedule_id: uuid.UUID | None
    target_date: date | None
    status: str
    planning_preferences: PlanningPreferences


class StudyGoalRepository(Protocol):
    """Reads and writes the records establishing a study goal touches."""

    def list_learners(self) -> tuple[LearnerRecord, ...]:
        """Every stored learner.

        The MVP has one. Returning them all rather than "the" learner keeps the
        decision about what to do with none, one, or several in the use case.
        """
        ...

    def add_learner(self, record: LearnerRecord) -> None:
        """Store a new learner."""
        ...

    def find_learning_program_id(self, code: str) -> uuid.UUID | None:
        """The identifier of the program with this code, or None."""
        ...

    def find_active_curriculum_version(
        self, learning_program_id: uuid.UUID
    ) -> CurriculumVersionSummary | None:
        """The program's active curriculum version, or None.

        At most one can exist: a partial unique index enforces it (ADR-011).
        """
        ...

    def find_examination_schedule(
        self, *, learning_program_id: uuid.UUID, cycle_label: str
    ) -> ExaminationScheduleRecord | None:
        """The program's published schedule for this cycle, or None."""
        ...

    def list_examination_periods(
        self, examination_schedule_id: uuid.UUID
    ) -> tuple[ExaminationPeriodRecord, ...]:
        """Every period of this schedule, in date order."""
        ...

    def find_active_study_goal(
        self, *, learner_id: uuid.UUID, learning_program_id: uuid.UUID
    ) -> StudyGoalRecord | None:
        """The learner's active goal for this program, or None.

        Goals that are paused, completed, or archived are history and are never
        rewritten by setting a new goal.
        """
        ...

    def add_study_goal(self, record: StudyGoalRecord) -> None:
        """Store a new study goal."""
        ...

    def update_study_goal(self, record: StudyGoalRecord) -> None:
        """Overwrite the stored goal identified by ``record.id``.

        Every writable column is written, including the planning preferences.
        The command serving this port does not manage preferences, so it copies
        the stored ones onto the record it writes; leaving them unwritten here
        instead would make the record carry a field one writer silently ignores.
        """
        ...
