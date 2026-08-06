"""Input and output structures for a learner's study goal.

A study goal binds one learner to the curriculum they are studying and the
outcome they are working toward. The outcome is either a published examination
cycle -- whose dates are a window, not a day -- or a plain target completion
date for a learner following no examination.

Two workflows share these structures. `StudyGoalRequest` and `StudyGoalSummary`
serve the `scripts.set_study_goal` command, which resolves a program by its code
and reports what a run changed. `NewStudyGoal`, `StudyGoalChanges`,
`StudyGoalDetail`, and `StudyGoalPage` serve GOAL-001 to GOAL-005, which address
records by identifier because a client holds identifiers rather than codes.

The weekly availability a goal carries has its own structures, in
`dto/availability.py`, and its planning preferences theirs, in
`dto/planning_preferences.py`; a goal detail embeds both rather than redescribing
them.

Neither carries a learner identifier inbound. The effective learner is resolved
server-side and never chosen by a client (docs/api/conventions.md).

Nothing here decides how a goal is stored or where the examination dates came
from; both are supplied through ports.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.application.dto.availability import WeeklyAvailability
from app.application.dto.planning_preferences import (
    NO_PLANNING_PREFERENCES,
    PlanningPreferences,
)


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

    id: uuid.UUID
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


@dataclass(frozen=True, slots=True)
class NewStudyGoal:
    """A goal a learner is asking to create (GOAL-001).

    There is no ``curriculum_version_id``. A goal binds to the program's
    *active* curriculum version, so a client cannot attach a learner to a draft
    or retired syllabus by naming its identifier. Accepting one later, once a
    reason exists to study an older version, is a compatible addition.

    Attributes:
        learning_program_id: The program to study.
        examination_schedule_id: The published cycle to aim at, if any.
        target_date: A plain completion date, if any. At least one of this and
            ``examination_schedule_id`` must be present.
        planning_preferences: How the learner wants a plan built. Empty by
            default, because a learner who names no preference has none rather
            than having the ones the product would have picked.
    """

    learning_program_id: uuid.UUID
    examination_schedule_id: uuid.UUID | None = None
    target_date: date | None = None
    planning_preferences: PlanningPreferences = NO_PLANNING_PREFERENCES


@dataclass(frozen=True, slots=True)
class StudyGoalChanges:
    """The fields a goal update asks to change (GOAL-004).

    A field left unset is not touched. Clearing needs its own flag for the same
    reason it does on a learner profile: a nullable field alone cannot say
    whether ``None`` means "leave it" or "remove it", and guessing wrong silently
    discards the learner's horizon.

    ``planning_preferences`` needs **no such flag**, and the asymmetry is
    deliberate. It replaces the whole group rather than merging into it, the way
    GOAL-005 replaces a whole week: the preferences named become the goal's
    preferences, and one left out of a supplied group is unset. An empty group is
    therefore a distinct value from no group at all, so ``None`` can mean "leave
    them alone" without any other statement becoming inexpressible -- where a
    bare ``target_date`` of ``None`` could not tell absence from a clear.
    """

    examination_schedule_id: uuid.UUID | None = None
    clear_examination_schedule: bool = False
    target_date: date | None = None
    clear_target_date: bool = False
    status: str | None = None
    planning_preferences: PlanningPreferences | None = None

    @property
    def is_empty(self) -> bool:
        """Whether the update asks for nothing at all."""
        return (
            self.examination_schedule_id is None
            and not self.clear_examination_schedule
            and self.target_date is None
            and not self.clear_target_date
            and self.status is None
            and self.planning_preferences is None
        )


@dataclass(frozen=True, slots=True)
class StudyGoalProgram:
    """The learning program a goal is bound to."""

    id: uuid.UUID
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class StudyGoalCurriculumVersion:
    """The curriculum version a goal is bound to."""

    id: uuid.UUID
    version_label: str
    status: str


@dataclass(frozen=True, slots=True)
class StudyGoalDetail:
    """One stored goal, with the reference data it points at resolved.

    The program and curriculum version are embedded rather than left as bare
    identifiers, because a client showing a goal would otherwise need two further
    requests to name what the learner is studying.

    `availability` is the week the learner has saved against this goal, which
    GOAL-005 writes. It is embedded for the same reason: the catalogue's original
    intent line for GOAL-003 promised an availability summary, and a screen
    showing a goal wants the week beside it rather than after a second request.
    A goal whose availability has never been saved carries an empty week.

    `planning_preferences` is embedded on the same grounds, and the catalogue's
    original intent line for GOAL-004 promised them here too. A goal whose
    learner has set none carries an empty set rather than a null, so no screen
    needs a branch for a goal stored before preferences existed.
    """

    id: uuid.UUID
    learner_id: uuid.UUID
    status: str
    target_date: date | None
    learning_program: StudyGoalProgram
    curriculum_version: StudyGoalCurriculumVersion
    examination: ExaminationGoalSummary | None
    availability: WeeklyAvailability
    planning_preferences: PlanningPreferences


@dataclass(frozen=True, slots=True)
class StudyGoalPage:
    """One page of a learner's goals, and how many they have in total."""

    goals: tuple[StudyGoalDetail, ...]
    total: int
    limit: int
    offset: int
