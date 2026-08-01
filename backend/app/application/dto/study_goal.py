"""Input and output structures for establishing a learner's study goal.

A study goal binds one learner to the curriculum they are studying and the
outcome they are working toward. The outcome is either a published examination
cycle -- whose dates are a window, not a day -- or a plain target completion
date for a learner following no examination.

Nothing here decides how a goal is stored or where the examination dates came
from; both are supplied through ports.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class RecordChange(StrEnum):
    """What setting a goal did to one record.

    Reported rather than inferred, so a repeat run can say plainly that it wrote
    nothing instead of leaving the caller to compare timestamps.
    """

    created = "created"
    updated = "updated"
    unchanged = "unchanged"


@dataclass(frozen=True, slots=True)
class StudyGoalRequest:
    """The learner's choice of curriculum and examination goal.

    Attributes:
        program_code: The learning program to study, such as ``gate-cse``. Its
            active curriculum version is the one the goal is bound to.
        learner_timezone: IANA timezone stored on the learner record when this
            request creates it. Supplied by the composition root, which is the
            only layer permitted to read configuration.
        examination_cycle_label: The published examination cycle to aim at, such
            as ``2027``. Omit it for a learner following no examination.
        target_date: A plain target completion date. Required only when no
            examination cycle is named; the two together are also accepted.
        learner_display_name: Optional name for a learner record this request
            creates. An existing learner is never renamed here.
    """

    program_code: str
    learner_timezone: str
    examination_cycle_label: str | None = None
    target_date: date | None = None
    learner_display_name: str | None = None


@dataclass(frozen=True, slots=True)
class ExaminationGoalSummary:
    """The examination cycle a goal aims at, and how far its dates can be trusted.

    ``window_starts_on`` and ``window_ends_on`` span the examination periods of
    the cycle -- the first sitting day to the last. They are not a claim that the
    learner sits the paper on any particular day inside it.
    """

    cycle_label: str
    name: str
    schedule_status: str
    source_reference: str
    source_checked_on: date
    organising_body: str | None
    window_starts_on: date | None
    window_ends_on: date | None

    @property
    def dates_may_change(self) -> bool:
        """Whether the source still describes these dates as liable to change."""
        return self.schedule_status == "provisional"


@dataclass(frozen=True, slots=True)
class StudyGoalSummary:
    """The learner, the goal, and what setting it changed."""

    learner_id: uuid.UUID
    learner_change: RecordChange
    study_goal_id: uuid.UUID
    study_goal_change: RecordChange
    status: str
    learning_program_code: str
    curriculum_version_label: str
    target_date: date | None
    examination: ExaminationGoalSummary | None

    @property
    def changed(self) -> bool:
        """Whether the run wrote anything at all."""
        return any(
            change is not RecordChange.unchanged
            for change in (self.learner_change, self.study_goal_change)
        )
