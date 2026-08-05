"""An in-memory stand-in for the examination schedule read port.

It holds published schedules and their periods, which nothing in the application
writes at runtime: they arrive through `scripts.seed_examination_schedule`.

Ordering matches the SQLAlchemy implementation -- schedules by descending cycle
label, periods by start date then type -- so a use case test and the real store
agree about what a page contains.
"""

import uuid
from collections.abc import Sequence

from app.application.ports.examination_schedule_repository import (
    ExaminationPeriodRecord,
    ExaminationScheduleRecord,
)


class FakeExaminationScheduleRepository:
    """Serves fixed schedules and periods from tuples."""

    def __init__(
        self,
        *,
        schedules: Sequence[ExaminationScheduleRecord] = (),
        periods: Sequence[ExaminationPeriodRecord] = (),
    ) -> None:
        self.schedules = tuple(schedules)
        self.periods = tuple(periods)

    def count_examination_schedules(self, learning_program_id: uuid.UUID | None) -> int:
        return len(self._matching(learning_program_id))

    def list_examination_schedules(
        self, *, learning_program_id: uuid.UUID | None, limit: int, offset: int
    ) -> tuple[ExaminationScheduleRecord, ...]:
        # Two passes, because the store orders by cycle label descending and
        # breaks the tie on an ascending identifier; one `reverse` cannot do both.
        by_identifier = sorted(self._matching(learning_program_id), key=lambda r: str(r.id))
        ordered = sorted(by_identifier, key=lambda record: record.cycle_label, reverse=True)
        return tuple(ordered[offset : offset + limit])

    def find_examination_schedule(
        self, examination_schedule_id: uuid.UUID
    ) -> ExaminationScheduleRecord | None:
        return next(
            (record for record in self.schedules if record.id == examination_schedule_id), None
        )

    def list_examination_periods(
        self, examination_schedule_ids: Sequence[uuid.UUID]
    ) -> tuple[ExaminationPeriodRecord, ...]:
        wanted = set(examination_schedule_ids)
        return tuple(
            sorted(
                (record for record in self.periods if record.examination_schedule_id in wanted),
                key=lambda record: (record.starts_on, record.period_type),
            )
        )

    def _matching(
        self, learning_program_id: uuid.UUID | None
    ) -> tuple[ExaminationScheduleRecord, ...]:
        if learning_program_id is None:
            return self.schedules
        return tuple(
            record for record in self.schedules if record.learning_program_id == learning_program_id
        )
