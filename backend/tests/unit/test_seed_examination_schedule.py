"""Behaviour of the examination schedule seed use case, against a fake store.

The properties under test are the ones that make the seed safe to run by hand,
in CI, and after a restore: it writes only what differs, it never deletes, and it
refuses a schedule that would misrepresent what a source published.
"""

import uuid
from datetime import date

import pytest

from app.application.dto.examination_schedule_seed import (
    ExaminationPeriodSeed,
    ExaminationScheduleSeed,
)
from app.application.use_cases.seed_examination_schedule import (
    InvalidExaminationScheduleSeedError,
    SeedExaminationSchedule,
    UnknownLearningProgramError,
)
from tests.unit.fake_examination_schedule_seed_repository import (
    FakeExaminationScheduleSeedRepository,
)

PROGRAM_CODE = "gate-cse"


def make_seed(**overrides) -> ExaminationScheduleSeed:
    """A schedule shaped like the bundled GATE 2027 one, with fields replaceable."""
    fields = {
        "program_code": PROGRAM_CODE,
        "cycle_label": "2027",
        "name": "GATE 2027",
        "organising_body": "IIT Madras",
        "source_reference": "https://gate2027.iitm.ac.in/",
        "source_checked_on": date(2026, 8, 1),
        "schedule_status": "provisional",
        "periods": (
            ExaminationPeriodSeed("registration", date(2026, 8, 14), date(2026, 9, 21)),
            ExaminationPeriodSeed("late_registration", date(2026, 9, 22), date(2026, 9, 30)),
            ExaminationPeriodSeed("examination", date(2027, 2, 6), date(2027, 2, 7)),
            ExaminationPeriodSeed("examination", date(2027, 2, 13), date(2027, 2, 14)),
            ExaminationPeriodSeed("examination", date(2027, 2, 20), date(2027, 2, 21)),
            ExaminationPeriodSeed("results", date(2027, 3, 19), date(2027, 3, 19)),
        ),
    }
    fields.update(overrides)
    return ExaminationScheduleSeed(**fields)


@pytest.fixture
def repository() -> FakeExaminationScheduleSeedRepository:
    return FakeExaminationScheduleSeedRepository({PROGRAM_CODE: uuid.uuid4()})


def test_first_run_stores_the_schedule_and_every_period(repository):
    result = SeedExaminationSchedule(repository)(make_seed())

    assert result.examination_schedule.created == 1
    assert result.examination_periods.created == 6
    assert len(repository.periods) == 6


def test_second_run_of_an_unchanged_schedule_writes_nothing(repository):
    seed_schedule = SeedExaminationSchedule(repository)
    seed_schedule(make_seed())

    result = seed_schedule(make_seed())

    assert result.changed is False
    assert result.examination_schedule.unchanged == 1
    assert result.examination_periods.unchanged == 6


def test_second_run_keeps_the_identifiers_the_first_run_created(repository):
    """A study goal points at a schedule by identifier; re-seeding must not move it."""
    seed_schedule = SeedExaminationSchedule(repository)
    seed_schedule(make_seed())
    original_schedule = set(repository.schedules)
    original_periods = set(repository.periods)

    seed_schedule(make_seed())

    assert set(repository.schedules) == original_schedule
    assert set(repository.periods) == original_periods


def test_the_three_examination_weekends_are_stored_as_separate_periods(repository):
    """A single 6-21 February range would put eleven non-sitting days in the window."""
    SeedExaminationSchedule(repository)(make_seed())

    sittings = sorted(
        (record.starts_on, record.ends_on)
        for record in repository.periods.values()
        if record.period_type == "examination"
    )

    assert sittings == [
        (date(2027, 2, 6), date(2027, 2, 7)),
        (date(2027, 2, 13), date(2027, 2, 14)),
        (date(2027, 2, 20), date(2027, 2, 21)),
    ]


def test_a_results_announcement_is_stored_as_a_single_day_period(repository):
    SeedExaminationSchedule(repository)(make_seed())

    results = next(
        record for record in repository.periods.values() if record.period_type == "results"
    )

    assert results.starts_on == results.ends_on == date(2027, 3, 19)


def test_a_corrected_end_date_updates_the_period_in_place(repository):
    seed_schedule = SeedExaminationSchedule(repository)
    seed_schedule(make_seed())
    before = {record.id for record in repository.periods.values()}

    moved = make_seed(
        periods=(
            ExaminationPeriodSeed("registration", date(2026, 8, 14), date(2026, 9, 28)),
            ExaminationPeriodSeed("examination", date(2027, 2, 6), date(2027, 2, 7)),
        )
    )
    result = seed_schedule(moved)

    assert result.examination_periods.updated == 1
    assert result.examination_periods.unchanged == 1
    assert {record.id for record in repository.periods.values()} == before
    registration = next(
        record for record in repository.periods.values() if record.period_type == "registration"
    )
    assert registration.ends_on == date(2026, 9, 28)


def test_a_period_dropped_from_the_source_keeps_its_row(repository):
    """The seed never deletes: a goal may already point at this cycle."""
    seed_schedule = SeedExaminationSchedule(repository)
    seed_schedule(make_seed())

    seed_schedule(
        make_seed(
            periods=(ExaminationPeriodSeed("examination", date(2027, 2, 6), date(2027, 2, 7)),)
        )
    )

    assert len(repository.periods) == 6


def test_a_confirmed_schedule_updates_a_provisional_one(repository):
    """The point of the status: it changes when the organising body confirms."""
    seed_schedule = SeedExaminationSchedule(repository)
    seed_schedule(make_seed())

    result = seed_schedule(make_seed(schedule_status="confirmed"))

    assert result.examination_schedule.updated == 1
    assert next(iter(repository.schedules.values())).schedule_status == "confirmed"


def test_a_schedule_for_an_unknown_learning_program_is_refused(repository):
    with pytest.raises(UnknownLearningProgramError) as excinfo:
        SeedExaminationSchedule(repository)(make_seed(program_code="gate-ee"))

    assert "gate-ee" in str(excinfo.value)
    assert repository.schedules == {}


def test_an_unknown_schedule_status_is_refused(repository):
    with pytest.raises(InvalidExaminationScheduleSeedError) as excinfo:
        SeedExaminationSchedule(repository)(make_seed(schedule_status="announced"))

    assert "announced" in str(excinfo.value)


def test_an_unknown_period_type_is_refused(repository):
    seed = make_seed(
        periods=(
            ExaminationPeriodSeed("counselling", date(2027, 4, 1), date(2027, 4, 2)),
            ExaminationPeriodSeed("examination", date(2027, 2, 6), date(2027, 2, 7)),
        )
    )

    with pytest.raises(InvalidExaminationScheduleSeedError) as excinfo:
        SeedExaminationSchedule(repository)(seed)

    assert "counselling" in str(excinfo.value)


def test_a_period_ending_before_it_starts_is_refused(repository):
    seed = make_seed(
        periods=(ExaminationPeriodSeed("examination", date(2027, 2, 7), date(2027, 2, 6)),)
    )

    with pytest.raises(InvalidExaminationScheduleSeedError):
        SeedExaminationSchedule(repository)(seed)


def test_a_schedule_with_no_examination_period_is_refused(repository):
    """Deadlines alone describe no examination to plan toward."""
    seed = make_seed(
        periods=(ExaminationPeriodSeed("registration", date(2026, 8, 14), date(2026, 9, 21)),)
    )

    with pytest.raises(InvalidExaminationScheduleSeedError) as excinfo:
        SeedExaminationSchedule(repository)(seed)

    assert "examination" in str(excinfo.value)


def test_a_schedule_with_no_periods_at_all_is_refused(repository):
    with pytest.raises(InvalidExaminationScheduleSeedError):
        SeedExaminationSchedule(repository)(make_seed(periods=()))


def test_two_periods_sharing_a_type_and_start_date_are_refused(repository):
    """That pair is the natural key; a duplicate would make the match ambiguous."""
    seed = make_seed(
        periods=(
            ExaminationPeriodSeed("examination", date(2027, 2, 6), date(2027, 2, 7)),
            ExaminationPeriodSeed("examination", date(2027, 2, 6), date(2027, 2, 8)),
        )
    )

    with pytest.raises(InvalidExaminationScheduleSeedError) as excinfo:
        SeedExaminationSchedule(repository)(seed)

    assert "2027-02-06" in str(excinfo.value)


def test_nothing_is_written_when_the_seed_is_invalid(repository):
    with pytest.raises(InvalidExaminationScheduleSeedError):
        SeedExaminationSchedule(repository)(make_seed(schedule_status="announced"))

    assert repository.schedules == {}
    assert repository.periods == {}


def test_two_programs_may_hold_a_schedule_for_the_same_cycle(repository):
    """A cycle label is unique within a program, not across the platform."""
    repository.learning_programs["gate-ee"] = uuid.uuid4()
    seed_schedule = SeedExaminationSchedule(repository)
    seed_schedule(make_seed())

    seed_schedule(make_seed(program_code="gate-ee", name="GATE 2027 Electrical"))

    assert len(repository.schedules) == 2
