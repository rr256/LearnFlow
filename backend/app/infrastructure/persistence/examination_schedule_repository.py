"""SQLAlchemy implementation of the examination schedule read port.

Serves EXM-001 and the schedule lookups the study-goal endpoints make. Separate
from `examination_schedule_seed_repository` for the reason the ports are
separate: this one cannot write, so a reader can trust it at a glance.

Ordering of a page is fixed here, because a page cannot be ordered after it has
been sliced. Which periods form the examination window is not decided here; that
rule lives in the application layer (ADR-013).

The session's transaction is owned by the caller. Nothing here commits.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.ports.examination_schedule_repository import (
    ExaminationPeriodRecord,
    ExaminationScheduleRecord,
)
from app.infrastructure.persistence.examination_schedule import (
    ExaminationPeriod,
    ExaminationSchedule,
)


class SqlAlchemyExaminationScheduleRepository:
    """Reads published examination schedules through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one unit of work."""
        self._session = session

    def count_examination_schedules(self, learning_program_id: uuid.UUID | None) -> int:
        """How many schedules match, ignoring any page window."""
        statement = select(func.count()).select_from(ExaminationSchedule)
        if learning_program_id is not None:
            statement = statement.where(
                ExaminationSchedule.learning_program_id == learning_program_id
            )
        return self._session.scalar(statement) or 0

    def list_examination_schedules(
        self, *, learning_program_id: uuid.UUID | None, limit: int, offset: int
    ) -> tuple[ExaminationScheduleRecord, ...]:
        """One page of published schedules, newest cycle first.

        Cycle labels are years for the programs LearnFlow ships with, so
        descending label order puts the cycle a learner is most likely preparing
        for at the top. `id` breaks a tie so a page boundary is stable.
        """
        statement = select(ExaminationSchedule)
        if learning_program_id is not None:
            statement = statement.where(
                ExaminationSchedule.learning_program_id == learning_program_id
            )
        models = self._session.scalars(
            statement.order_by(ExaminationSchedule.cycle_label.desc(), ExaminationSchedule.id)
            .limit(limit)
            .offset(offset)
        )
        return tuple(_schedule_record(model) for model in models)

    def find_examination_schedule(
        self, examination_schedule_id: uuid.UUID
    ) -> ExaminationScheduleRecord | None:
        """The schedule with this identifier, or None."""
        model = self._session.get(ExaminationSchedule, examination_schedule_id)
        return None if model is None else _schedule_record(model)

    def list_examination_periods(
        self, examination_schedule_ids: Sequence[uuid.UUID]
    ) -> tuple[ExaminationPeriodRecord, ...]:
        """Every period of every schedule named, in date order."""
        if not examination_schedule_ids:
            return ()
        models = self._session.scalars(
            select(ExaminationPeriod)
            .where(ExaminationPeriod.examination_schedule_id.in_(examination_schedule_ids))
            .order_by(ExaminationPeriod.starts_on, ExaminationPeriod.period_type)
        )
        return tuple(
            ExaminationPeriodRecord(
                id=model.id,
                examination_schedule_id=model.examination_schedule_id,
                period_type=model.period_type,
                starts_on=model.starts_on,
                ends_on=model.ends_on,
            )
            for model in models
        )


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
