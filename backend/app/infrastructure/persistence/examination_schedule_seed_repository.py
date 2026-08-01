"""SQLAlchemy implementation of the examination schedule seed repository port.

Maps the application's plain records onto the examination ORM models and back.
It stores what it is told: which records to write, and whether a difference
counts as a change, are decided by the use case
(docs/architecture/dependency-rules.md).

The session's transaction is owned by the caller. Nothing here commits, so a
seed run that fails half way leaves no partial schedule behind.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ports.examination_schedule_repository import (
    ExaminationPeriodRecord,
    ExaminationScheduleRecord,
)
from app.infrastructure.persistence.curriculum import LearningProgram
from app.infrastructure.persistence.examination_schedule import (
    ExaminationPeriod,
    ExaminationSchedule,
)


class SqlAlchemyExaminationScheduleSeedRepository:
    """Reads and writes examination schedule records through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one unit of work."""
        self._session = session

    def find_learning_program_id(self, code: str) -> uuid.UUID | None:
        """The identifier of the program with this code, or None."""
        return self._session.scalar(select(LearningProgram.id).where(LearningProgram.code == code))

    def find_examination_schedule(
        self, *, learning_program_id: uuid.UUID, cycle_label: str
    ) -> ExaminationScheduleRecord | None:
        """The program's schedule for this cycle, or None."""
        model = self._session.scalar(
            select(ExaminationSchedule).where(
                ExaminationSchedule.learning_program_id == learning_program_id,
                ExaminationSchedule.cycle_label == cycle_label,
            )
        )
        return None if model is None else _schedule_record(model)

    def add_examination_schedule(self, record: ExaminationScheduleRecord) -> None:
        """Store a new examination schedule."""
        self._session.add(
            ExaminationSchedule(
                id=record.id,
                learning_program_id=record.learning_program_id,
                cycle_label=record.cycle_label,
                name=record.name,
                organising_body=record.organising_body,
                source_reference=record.source_reference,
                source_checked_on=record.source_checked_on,
                schedule_status=record.schedule_status,
            )
        )

    def update_examination_schedule(self, record: ExaminationScheduleRecord) -> None:
        """Overwrite the stored schedule identified by ``record.id``."""
        model = self._session.get(ExaminationSchedule, record.id)
        if model is None:
            raise LookupError(f"Examination schedule {record.id} is not stored.")
        model.name = record.name
        model.organising_body = record.organising_body
        model.source_reference = record.source_reference
        model.source_checked_on = record.source_checked_on
        model.schedule_status = record.schedule_status

    def list_examination_periods(
        self, examination_schedule_id: uuid.UUID
    ) -> tuple[ExaminationPeriodRecord, ...]:
        """Every period of this schedule, in date order."""
        models = self._session.scalars(
            select(ExaminationPeriod)
            .where(ExaminationPeriod.examination_schedule_id == examination_schedule_id)
            .order_by(ExaminationPeriod.starts_on, ExaminationPeriod.period_type)
        )
        return tuple(_period_record(model) for model in models)

    def add_examination_period(self, record: ExaminationPeriodRecord) -> None:
        """Store a new examination period."""
        self._session.add(
            ExaminationPeriod(
                id=record.id,
                examination_schedule_id=record.examination_schedule_id,
                period_type=record.period_type,
                starts_on=record.starts_on,
                ends_on=record.ends_on,
            )
        )

    def update_examination_period(self, record: ExaminationPeriodRecord) -> None:
        """Overwrite the stored period identified by ``record.id``."""
        model = self._session.get(ExaminationPeriod, record.id)
        if model is None:
            raise LookupError(f"Examination period {record.id} is not stored.")
        model.period_type = record.period_type
        model.starts_on = record.starts_on
        model.ends_on = record.ends_on


def _schedule_record(model: ExaminationSchedule) -> ExaminationScheduleRecord:
    return ExaminationScheduleRecord(
        id=model.id,
        learning_program_id=model.learning_program_id,
        cycle_label=model.cycle_label,
        name=model.name,
        organising_body=model.organising_body,
        source_reference=model.source_reference,
        source_checked_on=model.source_checked_on,
        schedule_status=model.schedule_status,
    )


def _period_record(model: ExaminationPeriod) -> ExaminationPeriodRecord:
    return ExaminationPeriodRecord(
        id=model.id,
        examination_schedule_id=model.examination_schedule_id,
        period_type=model.period_type,
        starts_on=model.starts_on,
        ends_on=model.ends_on,
    )
