"""Create, read, and update a learner's study goals (GOAL-001 to GOAL-005).

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

**Availability is a whole week, replaced at once.** GOAL-005 takes the days the
learner can study and makes them the goal's week: a day the request does not name
is removed. One request and one transaction, so an edit spanning three days
cannot leave one saved and two lost. A day is named by its `snake_case` name, so
no numbering convention exists to get wrong (ADR-018).

Nothing here totals a week, compares two weeks, or derives a plan from one.
Availability is a planning input, and Milestone 3's planning code is what reads
it.
"""

import uuid
from collections.abc import Iterable, Sequence

from app.application.dto.availability import (
    MINUTES_IN_A_DAY,
    WEEKDAYS,
    AvailabilitySlotEntry,
    WeeklyAvailability,
    WeeklyAvailabilityRequest,
)
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
    AvailabilitySlotRecord,
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


class UnknownWeekdayError(StudyGoalManagementError):
    """The week names a day the database would refuse."""


class DuplicateWeekdayError(StudyGoalManagementError):
    """The week names the same day twice, so what it asks for is undefined."""


class AvailableMinutesOutOfRangeError(StudyGoalManagementError):
    """A day claims fewer than zero or more minutes than a day holds."""


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
        return self._detail(
            record,
            program=program,
            version=version,
            schedule=schedule,
            # A goal that did not exist a moment ago has no availability, so
            # this is the one path that states the empty week rather than
            # reading it back.
            availability=WeeklyAvailability(study_goal_id=record.id, slots=()),
        )

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
        # One query for the whole page's availability. A goal's examination
        # periods are still read per goal -- ADR-016 recorded that cost -- but
        # there is no reason to add a second N+1 beside it.
        weeks = self._weeks_for(record.id for record in records)
        return StudyGoalPage(
            goals=tuple(self._resolve(record, availability=weeks[record.id]) for record in records),
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

    def replace_availability(
        self, study_goal_id: uuid.UUID, request: WeeklyAvailabilityRequest
    ) -> WeeklyAvailability:
        """Make `request` the goal's whole weekly availability (GOAL-005).

        A replacement, not a merge: the days named become the week, and a day the
        request does not name is removed. An empty request therefore clears the
        goal's availability, which is how a learner takes it all back.

        A day whose minutes have not changed is left alone entirely, so saving
        the same week twice writes nothing -- the rule PRG-004 applies to a stage
        a topic already holds, for the same reason: a repeated form submission
        must not fail or churn rows on its second attempt.

        The caller owns the transaction: this method writes through the
        repository but never commits.

        Raises:
            UnknownWeekdayError: A day is not one of the seven.
            DuplicateWeekdayError: A day is named more than once.
            AvailableMinutesOutOfRangeError: A day's minutes fall outside 0 to
                1440.
            StudyGoalNotFoundError: No such goal is stored, or it belongs to
                another learner.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        requested = _validated_week(request)
        goal = self._require_own_goal(study_goal_id)

        stored = {
            record.day_of_week: record for record in self._goals.list_availability_slots([goal.id])
        }
        for day, minutes in requested.items():
            existing = stored.get(day)
            if existing is None:
                self._goals.add_availability_slot(
                    AvailabilitySlotRecord(
                        id=uuid.uuid4(),
                        study_goal_id=goal.id,
                        day_of_week=day,
                        available_minutes=minutes,
                    )
                )
            elif existing.available_minutes != minutes:
                self._goals.update_availability_slot(
                    AvailabilitySlotRecord(
                        id=existing.id,
                        study_goal_id=existing.study_goal_id,
                        day_of_week=day,
                        available_minutes=minutes,
                    )
                )
        for day, existing in stored.items():
            if day not in requested:
                self._goals.delete_availability_slot(existing.id)

        return WeeklyAvailability(
            study_goal_id=goal.id,
            slots=_week_order(
                AvailabilitySlotEntry(day_of_week=day, available_minutes=minutes)
                for day, minutes in requested.items()
            ),
        )

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

    def _weeks_for(
        self, study_goal_ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, WeeklyAvailability]:
        """The saved week of every goal named, keyed by goal identifier.

        A goal with nothing stored gets an empty week rather than being absent,
        so a caller never has to distinguish "no availability" from "goal not
        asked about".
        """
        identifiers = tuple(study_goal_ids)
        days: dict[uuid.UUID, list[AvailabilitySlotEntry]] = {
            identifier: [] for identifier in identifiers
        }
        for slot in self._goals.list_availability_slots(identifiers):
            days.setdefault(slot.study_goal_id, []).append(
                AvailabilitySlotEntry(
                    day_of_week=slot.day_of_week, available_minutes=slot.available_minutes
                )
            )
        return {
            identifier: WeeklyAvailability(study_goal_id=identifier, slots=_week_order(entries))
            for identifier, entries in days.items()
        }

    def _resolve(
        self, record: StudyGoalRecord, *, availability: WeeklyAvailability | None = None
    ) -> StudyGoalDetail:
        """Fill in the reference data a stored goal points at.

        `availability` is supplied by a caller that has already read a page of
        weeks in one query; a caller resolving one goal lets this read it.
        """
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
        return self._detail(
            record,
            program=program,
            version=version,
            schedule=schedule,
            availability=(
                self._weeks_for([record.id])[record.id] if availability is None else availability
            ),
        )

    def _detail(
        self,
        record: StudyGoalRecord,
        *,
        program: LearningProgramRecord,
        version: CurriculumVersionRecord,
        schedule: ExaminationScheduleRecord | None,
        availability: WeeklyAvailability,
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
            availability=availability,
        )


def _validated_week(request: WeeklyAvailabilityRequest) -> dict[str, int]:
    """The requested week as day-to-minutes, refusing what the database would.

    Checked here rather than only at the API boundary, because these are the
    rules the `CHECK` constraints express: failing them in the database would
    surface as an unexplained `500`, where refusing them here names the day at
    fault. A duplicate day has no database equivalent -- the unique key would see
    one row, not two -- so it can only be caught here.

    The rejected value is deliberately not repeated back. Naming the seven days a
    caller may use is what it actually needs.
    """
    week: dict[str, int] = {}
    for slot in request.slots:
        if slot.day_of_week not in WEEKDAYS:
            raise UnknownWeekdayError(
                f"That is not a day of the week. Use one of: {', '.join(WEEKDAYS)}."
            )
        if slot.day_of_week in week:
            raise DuplicateWeekdayError(
                f"{slot.day_of_week!r} is named more than once. Give each day at most "
                "one entry, holding all the time available on it."
            )
        if not 0 <= slot.available_minutes <= MINUTES_IN_A_DAY:
            raise AvailableMinutesOutOfRangeError(
                f"Available minutes for {slot.day_of_week!r} must be between 0 and "
                f"{MINUTES_IN_A_DAY}, the number of minutes in a day."
            )
        week[slot.day_of_week] = slot.available_minutes
    return week


def _week_order(entries: Iterable[AvailabilitySlotEntry]) -> tuple[AvailabilitySlotEntry, ...]:
    """The days given, in week order, Monday first.

    Sorted in the application rather than by the query, because Monday-first is
    presentation: nothing is stored that ranks one day above another, so a
    database `ORDER BY` would need a numbering the schema deliberately has not
    got (ADR-018).
    """
    return tuple(sorted(entries, key=lambda entry: WEEKDAYS.index(entry.day_of_week)))


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
