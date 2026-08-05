"""Unit tests for the examination schedule read use case (EXM-001).

The rule under test is the one ADR-013 exists to protect: the examination window
spans the sitting days alone, and the registration and results periods that
bracket it never widen it.
"""

import uuid
from datetime import date

from app.application.use_cases.read_examination_schedules import ReadExaminationSchedules
from tests.unit.fake_examination_schedule_repository import FakeExaminationScheduleRepository
from tests.unit.schedule_fixtures import (
    PROGRAM_ID,
    build_schedule,
    gate_2027_periods,
    period,
)


def build(schedules, periods) -> ReadExaminationSchedules:
    return ReadExaminationSchedules(
        FakeExaminationScheduleRepository(schedules=schedules, periods=periods)
    )


def test_the_window_spans_the_first_sitting_day_to_the_last():
    """Three separate weekends are one window, not three."""
    schedule = build_schedule()
    reader = build([schedule], gate_2027_periods(schedule.id))

    detail = reader.list_examination_schedules(
        learning_program_id=None, limit=25, offset=0
    ).schedules[0]

    assert detail.window_starts_on == date(2027, 2, 6)
    assert detail.window_ends_on == date(2027, 2, 21)


def test_registration_and_results_periods_do_not_widen_the_window():
    """They bracket the examination rather than being it; ADR-013."""
    schedule = build_schedule()
    reader = build([schedule], gate_2027_periods(schedule.id))

    detail = reader.list_examination_schedules(
        learning_program_id=None, limit=25, offset=0
    ).schedules[0]

    assert min(item.starts_on for item in detail.periods) < detail.window_starts_on
    assert max(item.ends_on for item in detail.periods) > detail.window_ends_on


def test_every_period_is_reported_so_registration_deadlines_stay_visible():
    schedule = build_schedule()
    reader = build([schedule], gate_2027_periods(schedule.id))

    detail = reader.list_examination_schedules(
        learning_program_id=None, limit=25, offset=0
    ).schedules[0]

    assert [item.period_type for item in detail.periods] == [
        "registration",
        "late_registration",
        "examination",
        "examination",
        "examination",
        "results",
    ]


def test_a_schedule_with_no_sitting_day_reports_no_window_rather_than_guessing():
    schedule = build_schedule()
    reader = build(
        [schedule],
        [period(schedule.id, "registration", date(2026, 8, 24), date(2026, 9, 26))],
    )

    detail = reader.list_examination_schedules(
        learning_program_id=None, limit=25, offset=0
    ).schedules[0]

    assert detail.window_starts_on is None
    assert detail.window_ends_on is None


def test_a_provisional_schedule_says_its_dates_may_change():
    reader = build([build_schedule(schedule_status="provisional")], [])

    detail = reader.list_examination_schedules(
        learning_program_id=None, limit=25, offset=0
    ).schedules[0]

    assert detail.dates_may_change is True


def test_a_confirmed_schedule_does_not_say_its_dates_may_change():
    reader = build([build_schedule(schedule_status="confirmed")], [])

    detail = reader.list_examination_schedules(
        learning_program_id=None, limit=25, offset=0
    ).schedules[0]

    assert detail.dates_may_change is False


def test_filtering_by_program_excludes_another_programs_schedules():
    mine = build_schedule(cycle_label="2027")
    theirs = build_schedule(cycle_label="2027", learning_program_id=uuid.uuid4())
    reader = build([mine, theirs], [])

    page = reader.list_examination_schedules(learning_program_id=PROGRAM_ID, limit=25, offset=0)

    assert [detail.id for detail in page.schedules] == [mine.id]


def test_the_total_counts_every_match_and_ignores_the_window():
    reader = build([build_schedule(cycle_label=label) for label in ("2026", "2027", "2028")], [])

    page = reader.list_examination_schedules(learning_program_id=None, limit=1, offset=0)

    assert len(page.schedules) == 1
    assert page.total == 3
    assert (page.limit, page.offset) == (1, 0)


def test_schedules_are_ordered_with_the_newest_cycle_first():
    reader = build([build_schedule(cycle_label=label) for label in ("2026", "2028", "2027")], [])

    page = reader.list_examination_schedules(learning_program_id=None, limit=25, offset=0)

    assert [detail.cycle_label for detail in page.schedules] == ["2028", "2027", "2026"]
