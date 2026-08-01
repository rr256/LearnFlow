"""Apply a published examination schedule to the store, safely and repeatably.

The rules are the curriculum seed's, applied to a different kind of reference
data (ADR-012): every record is located by a natural key, written only when a
field actually differs, and never deleted.

Natural keys, each matching a uniqueness rule the database already enforces:

    examination schedule   (learning program, cycle label)
    examination period     (examination schedule, period type, start date)

Keying a period on its start date rather than on its order means a corrected end
date updates the period in place, while a sitting moved to a different day reads
as a new period alongside the old one. That asymmetry is deliberate: a schedule
published a year ahead is expected to move, and a study goal may already point
at the cycle, so the seed records the correction without quietly discarding what
was published before. Deciding which superseded periods to retire is a separate,
explicit action -- there is no delete path here.
"""

import uuid
from collections.abc import Sequence
from datetime import date

from app.application.dto.examination_schedule_seed import (
    EXAMINATION_PERIOD_TYPE,
    EXAMINATION_PERIOD_TYPES,
    EXAMINATION_SCHEDULE_STATUSES,
    ExaminationPeriodSeed,
    ExaminationScheduleSeed,
    ExaminationScheduleSeedResult,
)
from app.application.dto.seed_outcome import SeedOutcome
from app.application.ports.examination_schedule_repository import (
    ExaminationPeriodRecord,
    ExaminationScheduleRecord,
    ExaminationScheduleSeedRepository,
)


class ExaminationScheduleSeedError(Exception):
    """An examination schedule seed could not be applied."""


class InvalidExaminationScheduleSeedError(ExaminationScheduleSeedError):
    """The seed contradicts itself or the vocabulary the schema accepts."""


class UnknownLearningProgramError(ExaminationScheduleSeedError):
    """No learning program carries the code the schedule names.

    A schedule belongs to a program the curriculum seed creates, so this means
    the curriculum has not been loaded into this database yet.
    """


class SeedExaminationSchedule:
    """Applies an `ExaminationScheduleSeed` through an `ExaminationScheduleSeedRepository`."""

    def __init__(self, repository: ExaminationScheduleSeedRepository) -> None:
        """Wire the use case.

        Args:
            repository: Where examination schedule records are read and written.
        """
        self._repository = repository

    def __call__(self, seed: ExaminationScheduleSeed) -> ExaminationScheduleSeedResult:
        """Apply `seed`, returning what was created, updated, and left alone.

        The caller owns the transaction: this method writes through the
        repository but never commits, so a failure part-way leaves nothing
        behind.

        Raises:
            InvalidExaminationScheduleSeedError: The seed is internally
                inconsistent or uses a value the schema does not accept.
            UnknownLearningProgramError: The learning program it names is not
                stored.
        """
        _validate(seed)

        program_id = self._repository.find_learning_program_id(seed.program_code)
        if program_id is None:
            raise UnknownLearningProgramError(
                f"No learning program carries the code {seed.program_code!r}. "
                "Load the curriculum first: python -m scripts.seed_curriculum"
            )

        schedule, schedule_outcome = self._apply_schedule(seed, program_id)
        period_outcome = self._apply_periods(seed, schedule.id)

        return ExaminationScheduleSeedResult(
            examination_schedule=schedule_outcome,
            examination_periods=period_outcome,
        )

    def _apply_schedule(
        self, seed: ExaminationScheduleSeed, program_id: uuid.UUID
    ) -> tuple[ExaminationScheduleRecord, SeedOutcome]:
        existing = self._repository.find_examination_schedule(
            learning_program_id=program_id, cycle_label=seed.cycle_label
        )
        if existing is None:
            record = ExaminationScheduleRecord(
                id=uuid.uuid4(),
                learning_program_id=program_id,
                cycle_label=seed.cycle_label,
                name=seed.name,
                organising_body=seed.organising_body,
                source_reference=seed.source_reference,
                source_checked_on=seed.source_checked_on,
                schedule_status=seed.schedule_status,
            )
            self._repository.add_examination_schedule(record)
            return record, SeedOutcome().with_created()

        desired = ExaminationScheduleRecord(
            id=existing.id,
            learning_program_id=existing.learning_program_id,
            cycle_label=existing.cycle_label,
            name=seed.name,
            organising_body=seed.organising_body,
            source_reference=seed.source_reference,
            source_checked_on=seed.source_checked_on,
            schedule_status=seed.schedule_status,
        )
        if desired == existing:
            return existing, SeedOutcome().with_unchanged()
        self._repository.update_examination_schedule(desired)
        return desired, SeedOutcome().with_updated()

    def _apply_periods(self, seed: ExaminationScheduleSeed, schedule_id: uuid.UUID) -> SeedOutcome:
        existing = {
            (record.period_type, record.starts_on): record
            for record in self._repository.list_examination_periods(schedule_id)
        }

        outcome = SeedOutcome()
        for period in seed.periods:
            match = existing.get((period.period_type, period.starts_on))
            record = ExaminationPeriodRecord(
                id=match.id if match else uuid.uuid4(),
                examination_schedule_id=schedule_id,
                period_type=period.period_type,
                starts_on=period.starts_on,
                ends_on=period.ends_on,
            )
            if match is None:
                self._repository.add_examination_period(record)
                outcome = outcome.with_created()
            elif match == record:
                outcome = outcome.with_unchanged()
            else:
                self._repository.update_examination_period(record)
                outcome = outcome.with_updated()

        return outcome


def _validate(seed: ExaminationScheduleSeed) -> None:
    """Reject a seed the database would refuse, or that hides an authoring slip."""
    if seed.schedule_status not in EXAMINATION_SCHEDULE_STATUSES:
        raise InvalidExaminationScheduleSeedError(
            f"Unknown examination schedule status {seed.schedule_status!r}. "
            f"Expected one of {', '.join(EXAMINATION_SCHEDULE_STATUSES)}."
        )
    if not seed.periods:
        raise InvalidExaminationScheduleSeedError(
            "An examination schedule seed must define at least one period."
        )

    for period in seed.periods:
        if period.period_type not in EXAMINATION_PERIOD_TYPES:
            raise InvalidExaminationScheduleSeedError(
                f"Unknown examination period type {period.period_type!r}. "
                f"Expected one of {', '.join(EXAMINATION_PERIOD_TYPES)}."
            )
        if period.ends_on < period.starts_on:
            raise InvalidExaminationScheduleSeedError(
                f"Examination period {period.period_type!r} starting {period.starts_on} "
                f"ends on {period.ends_on}, before it starts."
            )

    if not any(period.period_type == EXAMINATION_PERIOD_TYPE for period in seed.periods):
        raise InvalidExaminationScheduleSeedError(
            "An examination schedule seed must define at least one "
            f"{EXAMINATION_PERIOD_TYPE!r} period; the others are the deadlines around it."
        )

    _reject_duplicate_periods(seed.periods)


def _reject_duplicate_periods(periods: Sequence[ExaminationPeriodSeed]) -> None:
    """No two periods may share a type and a start date; that is their natural key."""
    seen: set[tuple[str, date]] = set()
    for period in periods:
        key = (period.period_type, period.starts_on)
        if key in seen:
            raise InvalidExaminationScheduleSeedError(
                f"Duplicate examination period {key[0]!r} starting {key[1]}."
            )
        seen.add(key)
