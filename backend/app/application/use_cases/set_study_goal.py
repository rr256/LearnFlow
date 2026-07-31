"""Establish the learner's curriculum and examination goal.

This is the first learner-owned write in LearnFlow, and it is deliberately the
smallest one that lets planning begin later: which curriculum the learner is
studying, and what they are working toward.

Two rules shape it.

**The examination is a window.** A goal that names an examination cycle stores a
reference to the published schedule, never a copied date. The window it reports
is derived from the schedule's examination periods -- first sitting day to last
-- so a learner is never shown a specific paper date that the examining body has
not announced, and a corrected schedule reaches every goal at once.

**A goal aims at something.** Either an examination cycle or a plain target
completion date must be present; a database CHECK enforces the same rule, so a
goal cannot exist without a horizon to plan against.

Running this twice is safe. It matches the learner's active goal for the
program, writes only what differs, and never touches a goal that is paused,
completed, or archived -- that is history, not a draft.
"""

import uuid
from collections.abc import Sequence
from datetime import date

from app.application.dto.examination_schedule_seed import EXAMINATION_PERIOD_TYPE
from app.application.dto.study_goal import (
    ExaminationGoalSummary,
    RecordChange,
    StudyGoalRequest,
    StudyGoalSummary,
)
from app.application.ports.examination_schedule_repository import (
    ExaminationPeriodRecord,
    ExaminationScheduleRecord,
)
from app.application.ports.study_goal_repository import (
    LearnerRecord,
    StudyGoalRecord,
    StudyGoalRepository,
)

ACTIVE_STATUS = "active"


class StudyGoalError(Exception):
    """A study goal could not be established."""


class CurriculumNotAvailableError(StudyGoalError):
    """The learning program, or an active curriculum version for it, is not stored."""


class ExaminationScheduleNotFoundError(StudyGoalError):
    """No published schedule is stored for the examination cycle the request names."""


class MissingGoalTargetError(StudyGoalError):
    """The request names neither an examination cycle nor a target date."""


class AmbiguousLearnerError(StudyGoalError):
    """More than one learner is stored, so "the local learner" is undefined.

    The MVP is single-learner by design. Choosing one arbitrarily would attach a
    goal to a learner the caller did not mean, so this stops instead.
    """


class SetStudyGoal:
    """Establishes a learner's study goal through a `StudyGoalRepository`."""

    def __init__(self, repository: StudyGoalRepository) -> None:
        """Wire the use case.

        Args:
            repository: Where the learner, the goal, and the reference data they
                point at are read and written.
        """
        self._repository = repository

    def __call__(self, request: StudyGoalRequest) -> StudyGoalSummary:
        """Establish the goal `request` describes, returning what it changed.

        The caller owns the transaction: this method writes through the
        repository but never commits.

        Raises:
            CurriculumNotAvailableError: The program or its active curriculum
                version is not stored.
            ExaminationScheduleNotFoundError: The examination cycle is not
                stored.
            MissingGoalTargetError: The request names nothing to aim at.
            AmbiguousLearnerError: More than one learner is stored.
        """
        if request.examination_cycle_label is None and request.target_date is None:
            raise MissingGoalTargetError(
                "A study goal must name an examination cycle, a target date, or both. "
                "The database enforces the same rule."
            )

        program_id = self._repository.find_learning_program_id(request.program_code)
        if program_id is None:
            raise CurriculumNotAvailableError(
                f"No learning program carries the code {request.program_code!r}. "
                "Load the curriculum first: python -m scripts.seed_curriculum"
            )

        version = self._repository.find_active_curriculum_version(program_id)
        if version is None:
            raise CurriculumNotAvailableError(
                f"Learning program {request.program_code!r} has no active curriculum version. "
                "Seed one as active before setting a goal against it."
            )

        schedule, periods = self._resolve_examination_schedule(request, program_id)
        learner, learner_change = self._resolve_learner(request)
        goal, goal_change = self._apply_goal(
            request,
            learner_id=learner.id,
            program_id=program_id,
            curriculum_version_id=version.id,
            examination_schedule_id=None if schedule is None else schedule.id,
        )

        return StudyGoalSummary(
            learner_id=learner.id,
            learner_change=learner_change,
            study_goal_id=goal.id,
            study_goal_change=goal_change,
            status=goal.status,
            learning_program_code=request.program_code,
            curriculum_version_label=version.version_label,
            target_date=goal.target_date,
            examination=None if schedule is None else _summarise(schedule, periods),
        )

    def _resolve_examination_schedule(
        self, request: StudyGoalRequest, program_id: uuid.UUID
    ) -> tuple[ExaminationScheduleRecord | None, tuple[ExaminationPeriodRecord, ...]]:
        if request.examination_cycle_label is None:
            return None, ()

        schedule = self._repository.find_examination_schedule(
            learning_program_id=program_id, cycle_label=request.examination_cycle_label
        )
        if schedule is None:
            raise ExaminationScheduleNotFoundError(
                f"No examination schedule is stored for {request.program_code!r} cycle "
                f"{request.examination_cycle_label!r}. Load it first: "
                "python -m scripts.seed_examination_schedule"
            )
        return schedule, self._repository.list_examination_periods(schedule.id)

    def _resolve_learner(self, request: StudyGoalRequest) -> tuple[LearnerRecord, RecordChange]:
        """Find the local learner, or create one.

        An existing learner is returned untouched. Renaming a learner or moving
        their timezone is a profile change with its own workflow; doing it as a
        side effect of setting a goal would overwrite a deliberate edit with a
        command-line default.
        """
        learners = self._repository.list_learners()
        if len(learners) > 1:
            raise AmbiguousLearnerError(
                f"{len(learners)} learners are stored, so the local learner is undefined. "
                "LearnFlow is single-learner until accounts exist."
            )
        if learners:
            return learners[0], RecordChange.unchanged

        record = LearnerRecord(
            id=uuid.uuid4(),
            display_name=request.learner_display_name,
            timezone=request.learner_timezone,
        )
        self._repository.add_learner(record)
        return record, RecordChange.created

    def _apply_goal(
        self,
        request: StudyGoalRequest,
        *,
        learner_id: uuid.UUID,
        program_id: uuid.UUID,
        curriculum_version_id: uuid.UUID,
        examination_schedule_id: uuid.UUID | None,
    ) -> tuple[StudyGoalRecord, RecordChange]:
        existing = self._repository.find_active_study_goal(
            learner_id=learner_id, learning_program_id=program_id
        )
        if existing is None:
            record = StudyGoalRecord(
                id=uuid.uuid4(),
                learner_id=learner_id,
                learning_program_id=program_id,
                curriculum_version_id=curriculum_version_id,
                examination_schedule_id=examination_schedule_id,
                target_date=request.target_date,
                status=ACTIVE_STATUS,
            )
            self._repository.add_study_goal(record)
            return record, RecordChange.created

        desired = StudyGoalRecord(
            id=existing.id,
            learner_id=existing.learner_id,
            learning_program_id=existing.learning_program_id,
            curriculum_version_id=curriculum_version_id,
            examination_schedule_id=examination_schedule_id,
            target_date=request.target_date,
            status=existing.status,
        )
        if desired == existing:
            return existing, RecordChange.unchanged
        self._repository.update_study_goal(desired)
        return desired, RecordChange.updated


def _summarise(
    schedule: ExaminationScheduleRecord, periods: Sequence[ExaminationPeriodRecord]
) -> ExaminationGoalSummary:
    starts_on, ends_on = _examination_window(periods)
    return ExaminationGoalSummary(
        cycle_label=schedule.cycle_label,
        name=schedule.name,
        schedule_status=schedule.schedule_status,
        source_reference=schedule.source_reference,
        source_checked_on=schedule.source_checked_on,
        organising_body=schedule.organising_body,
        window_starts_on=starts_on,
        window_ends_on=ends_on,
    )


def _examination_window(
    periods: Sequence[ExaminationPeriodRecord],
) -> tuple[date | None, date | None]:
    """The first and last day the examination is sat.

    Registration and results periods are excluded: they bracket the examination
    rather than being it, and including them would widen the window a plan is
    built against by months.

    Returns ``(None, None)`` when a stored schedule has no examination period,
    which the seed refuses to create but a hand-edited database could hold.
    """
    sittings = [period for period in periods if period.period_type == EXAMINATION_PERIOD_TYPE]
    if not sittings:
        return None, None
    return (
        min(period.starts_on for period in sittings),
        max(period.ends_on for period in sittings),
    )
