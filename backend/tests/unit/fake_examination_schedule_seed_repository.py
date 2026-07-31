"""An in-memory stand-in for the examination schedule seed repository port.

It enforces the uniqueness rules the real schema enforces -- one schedule per
program and cycle, one period per schedule, type, and start date -- so a use case
that would trip a database constraint trips this fake instead, without needing
PostgreSQL.
"""

import uuid

from app.application.ports.examination_schedule_repository import (
    ExaminationPeriodRecord,
    ExaminationScheduleRecord,
)


class FakeExaminationScheduleSeedRepository:
    """Stores examination schedule records in dictionaries."""

    def __init__(self, learning_programs: dict[str, uuid.UUID] | None = None) -> None:
        """Start with the learning programs the curriculum seed would have created."""
        self.learning_programs = dict(learning_programs or {})
        self.schedules: dict[uuid.UUID, ExaminationScheduleRecord] = {}
        self.periods: dict[uuid.UUID, ExaminationPeriodRecord] = {}

    def find_learning_program_id(self, code: str) -> uuid.UUID | None:
        return self.learning_programs.get(code)

    def find_examination_schedule(
        self, *, learning_program_id: uuid.UUID, cycle_label: str
    ) -> ExaminationScheduleRecord | None:
        return next(
            (
                record
                for record in self.schedules.values()
                if record.learning_program_id == learning_program_id
                and record.cycle_label == cycle_label
            ),
            None,
        )

    def add_examination_schedule(self, record: ExaminationScheduleRecord) -> None:
        clash = self.find_examination_schedule(
            learning_program_id=record.learning_program_id, cycle_label=record.cycle_label
        )
        if clash is not None:
            raise AssertionError(f"cycle {record.cycle_label!r} is already stored for this program")
        self.schedules[record.id] = record

    def update_examination_schedule(self, record: ExaminationScheduleRecord) -> None:
        self._require(record.id in self.schedules, f"examination schedule {record.id}")
        self.schedules[record.id] = record

    def list_examination_periods(
        self, examination_schedule_id: uuid.UUID
    ) -> tuple[ExaminationPeriodRecord, ...]:
        return tuple(
            sorted(
                (
                    record
                    for record in self.periods.values()
                    if record.examination_schedule_id == examination_schedule_id
                ),
                key=lambda record: (record.starts_on, record.period_type),
            )
        )

    def add_examination_period(self, record: ExaminationPeriodRecord) -> None:
        clash = next(
            (
                other
                for other in self.periods.values()
                if (other.examination_schedule_id, other.period_type, other.starts_on)
                == (record.examination_schedule_id, record.period_type, record.starts_on)
            ),
            None,
        )
        if clash is not None:
            raise AssertionError(
                f"period {record.period_type!r} starting {record.starts_on} is already stored"
            )
        self.periods[record.id] = record

    def update_examination_period(self, record: ExaminationPeriodRecord) -> None:
        self._require(record.id in self.periods, f"examination period {record.id}")
        self.periods[record.id] = record

    @staticmethod
    def _require(condition: bool, what: str) -> None:
        if not condition:
            raise AssertionError(f"{what} is not stored")
