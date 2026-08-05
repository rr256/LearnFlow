"""Read the published examination schedules a learner can aim at (EXM-001).

This is the read side of the examination schedule area. It writes nothing, and
the rows it returns are the ones `scripts.seed_examination_schedule` loads.

It exists so a learner can *choose* a cycle rather than type its label: before
this, a schedule reached a client only through a goal that already named one,
which a learner setting their first goal has not got.

The window is derived here rather than stored, per ADR-013, so a schedule the
examining body corrects reaches every reader at once. The provenance travels
with the dates -- the body, the source, the day it was read, and whether the
source still calls the dates provisional -- because a provisional date shown
without that word reads as settled fact.
"""

import uuid
from collections import defaultdict
from collections.abc import Sequence

from app.application.dto.examination_schedule import (
    ExaminationPeriodSummary,
    ExaminationScheduleDetail,
    ExaminationSchedulePage,
)
from app.application.ports.examination_schedule_repository import (
    ExaminationPeriodRecord,
    ExaminationScheduleRecord,
    ExaminationScheduleRepository,
)
from app.application.use_cases.examination_window import derive_examination_window


class ReadExaminationSchedules:
    """Serves the examination schedule reads through an `ExaminationScheduleRepository`."""

    def __init__(self, repository: ExaminationScheduleRepository) -> None:
        """Wire the use case.

        Args:
            repository: Where published schedules and their periods are read.
        """
        self._repository = repository

    def list_examination_schedules(
        self, *, learning_program_id: uuid.UUID | None, limit: int, offset: int
    ) -> ExaminationSchedulePage:
        """One page of published schedules, each with its window and its periods.

        Args:
            learning_program_id: Restrict to one program's schedules, or return
                every stored schedule when None.
            limit: How many schedules to return. The caller validates the bound;
                this reports back what it was given so a client can confirm the
                window it received.
            offset: How many schedules to skip.
        """
        schedules = self._repository.list_examination_schedules(
            learning_program_id=learning_program_id, limit=limit, offset=offset
        )
        periods = self._periods_by_schedule([schedule.id for schedule in schedules])
        return ExaminationSchedulePage(
            schedules=tuple(_detail(schedule, periods[schedule.id]) for schedule in schedules),
            total=self._repository.count_examination_schedules(learning_program_id),
            limit=limit,
            offset=offset,
        )

    def _periods_by_schedule(
        self, examination_schedule_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[ExaminationPeriodRecord]]:
        grouped: dict[uuid.UUID, list[ExaminationPeriodRecord]] = defaultdict(list)
        if not examination_schedule_ids:
            return grouped
        for period in self._repository.list_examination_periods(examination_schedule_ids):
            grouped[period.examination_schedule_id].append(period)
        return grouped


def _detail(
    schedule: ExaminationScheduleRecord, periods: Sequence[ExaminationPeriodRecord]
) -> ExaminationScheduleDetail:
    starts_on, ends_on = derive_examination_window(periods)
    return ExaminationScheduleDetail(
        id=schedule.id,
        learning_program_id=schedule.learning_program_id,
        cycle_label=schedule.cycle_label,
        name=schedule.name,
        organising_body=schedule.organising_body,
        source_reference=schedule.source_reference,
        source_checked_on=schedule.source_checked_on,
        schedule_status=schedule.schedule_status,
        window_starts_on=starts_on,
        window_ends_on=ends_on,
        periods=tuple(
            ExaminationPeriodSummary(
                period_type=period.period_type,
                starts_on=period.starts_on,
                ends_on=period.ends_on,
            )
            for period in sorted(periods, key=lambda record: (record.starts_on, record.period_type))
        ),
    )
