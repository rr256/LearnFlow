"""Output structures for reading a published examination schedule (EXM-001).

A schedule is reference data with provenance: it says which body published these
dates, where they were read from, when they were read, and whether the source
still calls them liable to change. Every one of those travels with the dates,
because a provisional date shown without that word reads as settled fact
(docs/domain/terminology.md).

The examination itself is reported as a **window** -- first sitting day to last
-- derived from the schedule's `examination` periods. It is never a single date:
an examining body that publishes three sitting weekends has not named the
learner's day. The remaining periods are reported alongside it, because the
registration deadlines are the nearest actionable dates a learner has (ADR-013).
"""

import uuid
from dataclasses import dataclass
from datetime import date

PROVISIONAL_STATUS = "provisional"


@dataclass(frozen=True, slots=True)
class ExaminationPeriodSummary:
    """One dated period of a schedule. A single-day event starts and ends on it."""

    period_type: str
    starts_on: date
    ends_on: date


@dataclass(frozen=True, slots=True)
class ExaminationScheduleDetail:
    """One published schedule, its provenance, and the window it defines.

    ``window_starts_on`` and ``window_ends_on`` are ``None`` together when the
    stored schedule holds no examination period. That is reported rather than
    guessed at.
    """

    id: uuid.UUID
    learning_program_id: uuid.UUID
    cycle_label: str
    name: str
    organising_body: str | None
    source_reference: str
    source_checked_on: date
    schedule_status: str
    window_starts_on: date | None
    window_ends_on: date | None
    periods: tuple[ExaminationPeriodSummary, ...]

    @property
    def dates_may_change(self) -> bool:
        """Whether the source still describes these dates as liable to change."""
        return self.schedule_status == PROVISIONAL_STATUS


@dataclass(frozen=True, slots=True)
class ExaminationSchedulePage:
    """One page of published schedules, and how many there are in total."""

    schedules: tuple[ExaminationScheduleDetail, ...]
    total: int
    limit: int
    offset: int
