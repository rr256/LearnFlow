"""The persistence ports for a published examination schedule.

`ExaminationScheduleSeedRepository` serves the seed that loads a schedule;
`ExaminationScheduleRepository` serves EXM-001, which reads it back. They share
the record types below rather than describing the same rows twice.

The records below are application-owned values, not ORM rows. Every identifier
is supplied by the caller rather than returned by the store, so a whole schedule
-- the cycle and its periods -- can be assembled before any of it is written.

As with the curriculum seed, the port offers storage primitives only. Deciding
what counts as a change, what to insert, and what to leave alone belongs to the
use case (docs/architecture/dependency-rules.md).

There is no delete. An examination period the source no longer lists keeps its
row, for the same reason curriculum records do: a study goal may already point
at the schedule, and a published date that moves is a correction to record, not
a history to erase.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ExaminationScheduleRecord:
    """A stored examination schedule for one cycle of a learning program."""

    id: uuid.UUID
    learning_program_id: uuid.UUID
    cycle_label: str
    name: str
    organising_body: str | None
    source_reference: str
    source_checked_on: date
    schedule_status: str


@dataclass(frozen=True, slots=True)
class ExaminationPeriodRecord:
    """A stored dated period of a schedule. A single-day event starts and ends on it."""

    id: uuid.UUID
    examination_schedule_id: uuid.UUID
    period_type: str
    starts_on: date
    ends_on: date


class ExaminationScheduleSeedRepository(Protocol):
    """Reads and writes the records an examination schedule seed run touches."""

    def find_learning_program_id(self, code: str) -> uuid.UUID | None:
        """The identifier of the program with this code, or None.

        A schedule belongs to a program the curriculum seed created, so this
        resolves rather than creates: a missing program means the curriculum has
        not been loaded yet.
        """
        ...

    def find_examination_schedule(
        self, *, learning_program_id: uuid.UUID, cycle_label: str
    ) -> ExaminationScheduleRecord | None:
        """The program's schedule for this cycle, or None."""
        ...

    def add_examination_schedule(self, record: ExaminationScheduleRecord) -> None:
        """Store a new examination schedule."""
        ...

    def update_examination_schedule(self, record: ExaminationScheduleRecord) -> None:
        """Overwrite the stored schedule identified by ``record.id``."""
        ...

    def list_examination_periods(
        self, examination_schedule_id: uuid.UUID
    ) -> tuple[ExaminationPeriodRecord, ...]:
        """Every period of this schedule, in date order."""
        ...

    def add_examination_period(self, record: ExaminationPeriodRecord) -> None:
        """Store a new examination period."""
        ...

    def update_examination_period(self, record: ExaminationPeriodRecord) -> None:
        """Overwrite the stored period identified by ``record.id``."""
        ...


class ExaminationScheduleRepository(Protocol):
    """Reads the published schedules a learner chooses between and aims at.

    Separate from the seed port above for the reason `curriculum_repository`
    records: a port that could also write is one a reviewer has to read twice
    before trusting a read path.

    `list_examination_periods` takes several schedule identifiers at once so
    listing a page of schedules stays two queries rather than one per schedule.
    """

    def count_examination_schedules(self, learning_program_id: uuid.UUID | None) -> int:
        """How many schedules match, ignoring any page window.

        Args:
            learning_program_id: Count only this program's schedules, or every
                stored schedule when ``None``.
        """
        ...

    def list_examination_schedules(
        self, *, learning_program_id: uuid.UUID | None, limit: int, offset: int
    ) -> tuple[ExaminationScheduleRecord, ...]:
        """One page of published schedules, ordered by cycle label.

        The order is fixed here rather than in the use case because a page is
        chosen by the store: slicing first and sorting afterwards would return a
        different set of rows for the same offset.
        """
        ...

    def find_examination_schedule(
        self, examination_schedule_id: uuid.UUID
    ) -> ExaminationScheduleRecord | None:
        """The schedule with this identifier, or None."""
        ...

    def list_examination_periods(
        self, examination_schedule_ids: Sequence[uuid.UUID]
    ) -> tuple[ExaminationPeriodRecord, ...]:
        """Every period of every schedule named, in date order."""
        ...
