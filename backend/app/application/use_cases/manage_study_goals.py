"""Create, read, and update a learner's study goals (GOAL-001 to GOAL-004).

The rules here are the ones ADR-013 fixed, expressed once so the endpoints and
the `scripts.set_study_goal` command cannot disagree about them.

**A goal aims at something.** An examination cycle, a target completion date, or
both -- never neither. A `CHECK` enforces the same rule, but failing it in the
database would surface as an unexplained `500`; refusing it here names the
offending fields instead.

**The examination is a window.** A goal stores a reference to the published
schedule, never a copied date, and the window it reports is derived from that
schedule's examination periods on every read. A corrected schedule therefore
reaches every goal pointing at it, and no learner is shown a paper date the
examining body has not announced.

**A goal binds to the program's active curriculum version.** The client chooses
a program, not a syllabus revision, so a learner cannot be attached to a draft or
retired version by naming its identifier. An existing goal keeps the version it
was created against, even after that version is retired, because it records what
the learner actually planned against.

**One active goal per program.** A second create for the same program is refused
rather than silently replacing the first: the existing goal is what any plan was
built from, and overwriting it on a repeated form submission would discard it.
Editing goes through GOAL-004.
"""

import uuid
from collections.abc import Sequence

from app.application.dto.study_goal import (
    ExaminationGoalSummary,
    NewStudyGoal,
    StudyGoalChanges,
    StudyGoalCurriculumVersion,
    StudyGoalDetail,
    StudyGoalPage,
    StudyGoalProgram,
)
from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
)
from app.application.ports.examination_schedule_repository import (
    ExaminationPeriodRecord,
    ExaminationScheduleRecord,
    ExaminationScheduleRepository,
)
from app.application.ports.learner_repository import LearnerRepository
from app.application.ports.study_goal_management_repository import (
    StudyGoalManagementRepository,
)
from app.application.ports.study_goal_repository import StudyGoalRecord
from app.application.use_cases.examination_window import derive_examination_window
from app.application.use_cases.local_learner import resolve_local_learner

ACTIVE_STATUS = "active"

STUDY_GOAL_STATUSES: tuple[str, ...] = ("active", "paused", "completed", "archived")
"""Statuses `study_goals.status` accepts, mirroring the database `CHECK`."""


class StudyGoalManagementError(Exception):
    """A study goal could not be created, read, or updated as asked."""


class LearnerNotSetUpError(StudyGoalManagementError):
    """No learner exists yet, so there is nobody to own a goal."""


class StudyGoalNotFoundError(StudyGoalManagementError):
    """No goal with the requested identifier belongs to the local learner."""


class UnknownReferenceError(StudyGoalManagementError):
    """A record the request points at is not stored.

    ``field`` names the request field at fault, so the API can report which one
    rather than making a caller guess.
    """

    def __init__(self, message: str, *, field: str) -> None:
        """Record the failure and the request field responsible for it."""
        super().__init__(message)
        self.field = field


class StudyGoalIntegrityError(StudyGoalManagementError):
    """A stored goal points at reference data that is no longer stored.

    Foreign keys make this unreachable through the API. It is raised rather than
    papered over so a hand-edited database surfaces as a reported failure instead
    of a response with fields quietly missing. Distinct from
    `UnknownReferenceError`, which is always a caller's mistake.
    """


class MissingGoalTargetError(StudyGoalManagementError):
    """The resulting goal would aim at neither an examination cycle nor a date."""


class EmptyGoalUpdateError(StudyGoalManagementError):
    """The update names no field to change."""


class UnknownGoalStatusError(StudyGoalManagementError):
    """The update names a status the database would refuse."""


class ActiveGoalExistsError(StudyGoalManagementError):
    """The learner already has an active goal for this learning program."""


class ManageStudyGoals:
    """Serves the study-goal endpoints through the ports below."""

    def __init__(
        self,
        *,
        learners: LearnerRepository,
        goals: StudyGoalManagementRepository,
        schedules: ExaminationScheduleRepository,
    ) -> None:
        """Wire the use case.

        Args:
            learners: Where the effective learner is resolved.
            goals: Where goals and the curriculum they bind to are read and
                written.
            schedules: Where a published examination schedule and its periods are
                read, so the window a goal reports is always derived from the
                source.
        """
        self._learners = learners
        self._goals = goals
        self._schedules = schedules

    def create(self, request: NewStudyGoal) -> StudyGoalDetail:
        """Create the goal `request` describes.

        The caller owns the transaction: this method writes through the
        repository but never commits.

        Raises:
            LearnerNotSetUpError: No learner exists to own the goal.
            UnknownReferenceError: The program or examination schedule is not
                stored, or the schedule belongs to another program.
            MissingGoalTargetError: The request names nothing to aim at.
            ActiveGoalExistsError: The learner already has an active goal for
                this program.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        if request.examination_schedule_id is None and request.target_date is None:
            raise MissingGoalTargetError(
                "A study goal must name an examination schedule, a target date, or both."
            )

        learner = resolve_local_learner(self._learners)
        if learner is None:
            raise LearnerNotSetUpError(
                "No learner profile exists yet. Create one before setting a study goal."
            )

        program = self._require_program(request.learning_program_id)
        version = self._goals.find_active_curriculum_version(program.id)
        if version is None:
            raise UnknownReferenceError(
                f"Learning program {program.code!r} has no active curriculum version to "
                "study, so a goal cannot be bound to one.",
                field="learning_program_id",
            )

        schedule = self._require_schedule(request.examination_schedule_id, program.id)

        if (
            self._goals.find_active_study_goal(
                learner_id=learner.id, learning_program_id=program.id
            )
            is not None
        ):
            raise ActiveGoalExistsError(
                f"An active study goal already exists for {program.code!r}. "
                "Update that goal rather than creating a second one."
            )

        record = StudyGoalRecord(
            id=uuid.uuid4(),
            learner_id=learner.id,
            learning_program_id=program.id,
            curriculum_version_id=version.id,
            examination_schedule_id=None if schedule is None else schedule.id,
            target_date=request.target_date,
            status=ACTIVE_STATUS,
        )
        self._goals.add_study_goal(record)
        return self._detail(record, program=program, version=version, schedule=schedule)

    def list_study_goals(self, *, limit: int, offset: int) -> StudyGoalPage:
        """One page of the local learner's goals.

        A learner who has not been created yet has no goals, which is an empty
        page rather than a failure: a client listing goals before setup has run
        is asking a reasonable question.

        Raises:
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        learner = resolve_local_learner(self._learners)
        if learner is None:
            return StudyGoalPage(goals=(), total=0, limit=limit, offset=offset)

        records = self._goals.list_study_goals(learner_id=learner.id, limit=limit, offset=offset)
        return StudyGoalPage(
            goals=tuple(self._resolve(record) for record in records),
            total=self._goals.count_study_goals(learner.id),
            limit=limit,
            offset=offset,
        )

    def read(self, study_goal_id: uuid.UUID) -> StudyGoalDetail:
        """One goal belonging to the local learner.

        Raises:
            StudyGoalNotFoundError: No such goal is stored, or it belongs to
                another learner.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        return self._resolve(self._require_own_goal(study_goal_id))

    def update(self, study_goal_id: uuid.UUID, changes: StudyGoalChanges) -> StudyGoalDetail:
        """Apply `changes` to one of the local learner's goals.

        The caller owns the transaction: this method writes through the
        repository but never commits.

        Raises:
            EmptyGoalUpdateError: The update names no field to change.
            StudyGoalNotFoundError: No such goal is stored, or it belongs to
                another learner.
            UnknownReferenceError: The examination schedule is not stored, or
                belongs to another program.
            UnknownGoalStatusError: The status is not one the database accepts.
            MissingGoalTargetError: The result would aim at nothing.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        if changes.is_empty:
            raise EmptyGoalUpdateError("A goal update must name at least one field to change.")
        if changes.status is not None and changes.status not in STUDY_GOAL_STATUSES:
            raise UnknownGoalStatusError(
                f"{changes.status!r} is not a study goal status. "
                f"Use one of: {', '.join(STUDY_GOAL_STATUSES)}."
            )

        existing = self._require_own_goal(study_goal_id)
        schedule_id = _new_examination_schedule_id(existing, changes)
        target_date = existing.target_date if changes.target_date is None else changes.target_date
        if changes.clear_target_date:
            target_date = None

        if schedule_id is None and target_date is None:
            raise MissingGoalTargetError(
                "A study goal must keep an examination schedule, a target date, or both. "
                "This update would leave it aiming at neither."
            )

        schedule = self._require_schedule(schedule_id, existing.learning_program_id)
        updated = StudyGoalRecord(
            id=existing.id,
            learner_id=existing.learner_id,
            learning_program_id=existing.learning_program_id,
            curriculum_version_id=existing.curriculum_version_id,
            examination_schedule_id=None if schedule is None else schedule.id,
            target_date=target_date,
            status=changes.status or existing.status,
        )
        if updated != existing:
            self._goals.update_study_goal(updated)
        return self._resolve(updated)

    def _require_own_goal(self, study_goal_id: uuid.UUID) -> StudyGoalRecord:
        """The goal, if it exists and belongs to the local learner.

        A goal owned by somebody else is reported as missing rather than
        forbidden. `docs/api/conventions.md` treats "not visible to the caller"
        as a `404`, and saying "that exists but is not yours" would confirm a
        record a caller may not read.
        """
        learner = resolve_local_learner(self._learners)
        goal = None if learner is None else self._goals.find_study_goal(study_goal_id)
        if goal is None or learner is None or goal.learner_id != learner.id:
            raise StudyGoalNotFoundError(
                f"No study goal is stored with identifier {study_goal_id}."
            )
        return goal

    def _require_program(self, learning_program_id: uuid.UUID) -> LearningProgramRecord:
        program = self._goals.find_learning_program(learning_program_id)
        if program is None:
            raise UnknownReferenceError(
                f"No learning program is stored with identifier {learning_program_id}.",
                field="learning_program_id",
            )
        return program

    def _require_schedule(
        self, examination_schedule_id: uuid.UUID | None, learning_program_id: uuid.UUID
    ) -> ExaminationScheduleRecord | None:
        """The named schedule, checked to belong to the goal's own program.

        A schedule from another program would give the learner a window for an
        examination they are not studying for, which no database constraint
        forbids -- `study_goals` references the schedule and the program
        independently.
        """
        if examination_schedule_id is None:
            return None
        schedule = self._schedules.find_examination_schedule(examination_schedule_id)
        if schedule is None:
            raise UnknownReferenceError(
                f"No examination schedule is stored with identifier {examination_schedule_id}.",
                field="examination_schedule_id",
            )
        if schedule.learning_program_id != learning_program_id:
            raise UnknownReferenceError(
                f"Examination schedule {examination_schedule_id} belongs to a different "
                "learning program than this goal.",
                field="examination_schedule_id",
            )
        return schedule

    def _resolve(self, record: StudyGoalRecord) -> StudyGoalDetail:
        """Fill in the reference data a stored goal points at."""
        program = self._goals.find_learning_program(record.learning_program_id)
        if program is None:
            raise StudyGoalIntegrityError(
                f"Study goal {record.id} references learning program "
                f"{record.learning_program_id}, which is not stored."
            )
        version = self._goals.find_curriculum_version(record.curriculum_version_id)
        if version is None:
            raise StudyGoalIntegrityError(
                f"Study goal {record.id} references curriculum version "
                f"{record.curriculum_version_id}, which is not stored."
            )
        schedule = (
            None
            if record.examination_schedule_id is None
            else self._schedules.find_examination_schedule(record.examination_schedule_id)
        )
        return self._detail(record, program=program, version=version, schedule=schedule)

    def _detail(
        self,
        record: StudyGoalRecord,
        *,
        program: LearningProgramRecord,
        version: CurriculumVersionRecord,
        schedule: ExaminationScheduleRecord | None,
    ) -> StudyGoalDetail:
        return StudyGoalDetail(
            id=record.id,
            learner_id=record.learner_id,
            status=record.status,
            target_date=record.target_date,
            learning_program=StudyGoalProgram(id=program.id, code=program.code, name=program.name),
            curriculum_version=StudyGoalCurriculumVersion(
                id=version.id, version_label=version.version_label, status=version.status
            ),
            examination=(
                None
                if schedule is None
                else _summarise(schedule, self._schedules.list_examination_periods([schedule.id]))
            ),
        )


def _new_examination_schedule_id(
    existing: StudyGoalRecord, changes: StudyGoalChanges
) -> uuid.UUID | None:
    if changes.clear_examination_schedule:
        return None
    if changes.examination_schedule_id is not None:
        return changes.examination_schedule_id
    return existing.examination_schedule_id


def _summarise(
    schedule: ExaminationScheduleRecord, periods: Sequence[ExaminationPeriodRecord]
) -> ExaminationGoalSummary:
    starts_on, ends_on = derive_examination_window(periods)
    return ExaminationGoalSummary(
        id=schedule.id,
        cycle_label=schedule.cycle_label,
        name=schedule.name,
        schedule_status=schedule.schedule_status,
        source_reference=schedule.source_reference,
        source_checked_on=schedule.source_checked_on,
        organising_body=schedule.organising_body,
        window_starts_on=starts_on,
        window_ends_on=ends_on,
    )
