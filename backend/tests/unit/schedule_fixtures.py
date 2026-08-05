"""Examination schedule records shared by the onboarding tests.

The periods mirror the bundled GATE 2027 schedule in
`backend/scripts/gate_cse_examination_schedule.json`: three separate sitting
weekends, bracketed by registration and results. That shape is what makes the
window rule worth testing -- a single weekend would pass under a naive
first-to-last derivation too.

These are test fixtures, not curriculum content: no GATE CSE syllabus data is
expressed here.
"""

import uuid
from datetime import date

from app.application.ports.examination_schedule_repository import (
    ExaminationPeriodRecord,
    ExaminationScheduleRecord,
)

PROGRAM_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


def build_schedule(
    *,
    cycle_label: str = "2027",
    schedule_status: str = "provisional",
    learning_program_id: uuid.UUID = PROGRAM_ID,
) -> ExaminationScheduleRecord:
    """A published schedule with the provenance every stored schedule carries."""
    return ExaminationScheduleRecord(
        id=uuid.uuid4(),
        learning_program_id=learning_program_id,
        cycle_label=cycle_label,
        name=f"GATE {cycle_label}",
        organising_body="IIT Madras",
        source_reference="https://example.test/schedule",
        source_checked_on=date(2026, 8, 1),
        schedule_status=schedule_status,
    )


def period(
    examination_schedule_id: uuid.UUID, period_type: str, starts_on: date, ends_on: date
) -> ExaminationPeriodRecord:
    """One dated period of a schedule."""
    return ExaminationPeriodRecord(
        id=uuid.uuid4(),
        examination_schedule_id=examination_schedule_id,
        period_type=period_type,
        starts_on=starts_on,
        ends_on=ends_on,
    )


def gate_2027_periods(
    examination_schedule_id: uuid.UUID,
) -> tuple[ExaminationPeriodRecord, ...]:
    """Registration, late registration, three sitting weekends, and results."""
    return (
        period(examination_schedule_id, "registration", date(2026, 8, 24), date(2026, 9, 26)),
        period(examination_schedule_id, "late_registration", date(2026, 9, 27), date(2026, 10, 8)),
        period(examination_schedule_id, "examination", date(2027, 2, 6), date(2027, 2, 7)),
        period(examination_schedule_id, "examination", date(2027, 2, 13), date(2027, 2, 14)),
        period(examination_schedule_id, "examination", date(2027, 2, 20), date(2027, 2, 21)),
        period(examination_schedule_id, "results", date(2027, 3, 19), date(2027, 3, 19)),
    )
