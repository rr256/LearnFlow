"""Behaviour of the study goal use case, against a fake store.

The properties under test are what make the goal honest and repeatable: the
examination is reported as a window derived from the published sitting days, a
goal always aims at something, and setting the same goal twice writes nothing.
"""

import uuid
from datetime import date

import pytest

from app.application.dto.study_goal import RecordChange, StudyGoalRequest
from app.application.ports.examination_schedule_repository import (
    ExaminationPeriodRecord,
    ExaminationScheduleRecord,
)
from app.application.ports.study_goal_repository import CurriculumVersionSummary
from app.application.use_cases.set_study_goal import (
    AmbiguousLearnerError,
    CurriculumNotAvailableError,
    ExaminationScheduleNotFoundError,
    MissingGoalTargetError,
    SetStudyGoal,
)
from tests.unit.fake_study_goal_repository import FakeStudyGoalRepository

PROGRAM_CODE = "gate-cse"
PROGRAM_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
VERSION_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
SCHEDULE_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
TIMEZONE = "Asia/Kolkata"


def make_schedule() -> ExaminationScheduleRecord:
    return ExaminationScheduleRecord(
        id=SCHEDULE_ID,
        learning_program_id=PROGRAM_ID,
        cycle_label="2027",
        name="GATE 2027",
        organising_body="IIT Madras",
        source_reference="https://gate2027.iitm.ac.in/",
        source_checked_on=date(2026, 7, 31),
        schedule_status="provisional",
    )


def make_periods() -> tuple[ExaminationPeriodRecord, ...]:
    """The bundled GATE 2027 periods: deadlines around three sitting weekends."""
    spans = (
        ("registration", date(2026, 8, 14), date(2026, 9, 21)),
        ("late_registration", date(2026, 9, 22), date(2026, 9, 30)),
        ("examination", date(2027, 2, 6), date(2027, 2, 7)),
        ("examination", date(2027, 2, 13), date(2027, 2, 14)),
        ("examination", date(2027, 2, 20), date(2027, 2, 21)),
        ("results", date(2027, 3, 19), date(2027, 3, 19)),
    )
    return tuple(
        ExaminationPeriodRecord(
            id=uuid.uuid4(),
            examination_schedule_id=SCHEDULE_ID,
            period_type=period_type,
            starts_on=starts_on,
            ends_on=ends_on,
        )
        for period_type, starts_on, ends_on in spans
    )


@pytest.fixture
def repository() -> FakeStudyGoalRepository:
    return FakeStudyGoalRepository(
        learning_programs={PROGRAM_CODE: PROGRAM_ID},
        active_versions={PROGRAM_ID: CurriculumVersionSummary(id=VERSION_ID, version_label="2027")},
        schedules=(make_schedule(),),
        periods=make_periods(),
    )


def make_request(**overrides) -> StudyGoalRequest:
    fields = {
        "program_code": PROGRAM_CODE,
        "learner_timezone": TIMEZONE,
        "examination_cycle_label": "2027",
    }
    fields.update(overrides)
    return StudyGoalRequest(**fields)


def test_first_run_creates_the_learner_and_the_goal(repository):
    summary = SetStudyGoal(repository)(make_request())

    assert summary.learner_change is RecordChange.created
    assert summary.study_goal_change is RecordChange.created
    assert summary.status == "active"
    assert len(repository.learners) == 1
    assert len(repository.goals) == 1


def test_the_goal_is_bound_to_the_active_curriculum_version(repository):
    summary = SetStudyGoal(repository)(make_request())

    assert summary.curriculum_version_label == "2027"
    assert next(iter(repository.goals.values())).curriculum_version_id == VERSION_ID


def test_the_examination_window_spans_the_first_and_last_sitting_days(repository):
    """6 February to 21 February: the outer bounds of the three published weekends."""
    summary = SetStudyGoal(repository)(make_request())

    assert summary.examination is not None
    assert summary.examination.window_starts_on == date(2027, 2, 6)
    assert summary.examination.window_ends_on == date(2027, 2, 21)


def test_registration_and_results_periods_are_outside_the_examination_window(repository):
    """Including them would widen the window a plan is built against by months."""
    summary = SetStudyGoal(repository)(make_request())

    assert summary.examination is not None
    assert summary.examination.window_starts_on > date(2026, 9, 30)
    assert summary.examination.window_ends_on < date(2027, 3, 19)


def test_no_single_examination_date_is_recorded_on_the_goal(repository):
    """The organising body has not published the Computer Science paper's day."""
    SetStudyGoal(repository)(make_request())

    assert next(iter(repository.goals.values())).target_date is None


def test_the_goal_stores_a_reference_to_the_schedule_not_a_copy_of_its_dates(repository):
    """A revised schedule then reaches every goal pointing at it."""
    SetStudyGoal(repository)(make_request())

    assert next(iter(repository.goals.values())).examination_schedule_id == SCHEDULE_ID


def test_a_provisional_schedule_reports_that_its_dates_may_change(repository):
    summary = SetStudyGoal(repository)(make_request())

    assert summary.examination is not None
    assert summary.examination.dates_may_change is True
    assert summary.examination.source_reference == "https://gate2027.iitm.ac.in/"
    assert summary.examination.source_checked_on == date(2026, 7, 31)


def test_a_confirmed_schedule_reports_that_its_dates_are_settled():
    confirmed = ExaminationScheduleRecord(
        id=SCHEDULE_ID,
        learning_program_id=PROGRAM_ID,
        cycle_label="2027",
        name="GATE 2027",
        organising_body="IIT Madras",
        source_reference="https://gate2027.iitm.ac.in/",
        source_checked_on=date(2026, 12, 1),
        schedule_status="confirmed",
    )
    repository = FakeStudyGoalRepository(
        learning_programs={PROGRAM_CODE: PROGRAM_ID},
        active_versions={PROGRAM_ID: CurriculumVersionSummary(id=VERSION_ID, version_label="2027")},
        schedules=(confirmed,),
        periods=make_periods(),
    )

    summary = SetStudyGoal(repository)(make_request())

    assert summary.examination is not None
    assert summary.examination.dates_may_change is False


def test_setting_the_same_goal_twice_writes_nothing(repository):
    set_goal = SetStudyGoal(repository)
    set_goal(make_request())

    summary = set_goal(make_request())

    assert summary.changed is False
    assert summary.learner_change is RecordChange.unchanged
    assert summary.study_goal_change is RecordChange.unchanged
    assert len(repository.goals) == 1


def test_changing_the_examination_cycle_updates_the_existing_active_goal(repository):
    later = ExaminationScheduleRecord(
        id=uuid.uuid4(),
        learning_program_id=PROGRAM_ID,
        cycle_label="2028",
        name="GATE 2028",
        organising_body=None,
        source_reference="https://gate2028.example/",
        source_checked_on=date(2027, 4, 1),
        schedule_status="provisional",
    )
    repository.schedules = (*repository.schedules, later)
    set_goal = SetStudyGoal(repository)
    set_goal(make_request())
    original_id = next(iter(repository.goals))

    summary = set_goal(make_request(examination_cycle_label="2028"))

    assert summary.study_goal_change is RecordChange.updated
    assert summary.study_goal_id == original_id
    assert len(repository.goals) == 1


def test_an_existing_learner_is_reused_and_left_untouched(repository):
    """Renaming a learner is a profile change, not a side effect of setting a goal."""
    set_goal = SetStudyGoal(repository)
    set_goal(make_request(learner_display_name="Asha"))

    summary = set_goal(make_request(learner_display_name="Someone else"))

    assert summary.learner_change is RecordChange.unchanged
    assert repository.learners[summary.learner_id].display_name == "Asha"


def test_the_learner_is_created_with_the_configured_timezone(repository):
    summary = SetStudyGoal(repository)(make_request(learner_timezone="Europe/Berlin"))

    assert repository.learners[summary.learner_id].timezone == "Europe/Berlin"


def test_a_target_date_alone_is_a_valid_goal(repository):
    """A learner following no examination still needs a horizon."""
    summary = SetStudyGoal(repository)(
        make_request(examination_cycle_label=None, target_date=date(2027, 6, 30))
    )

    assert summary.examination is None
    assert summary.target_date == date(2027, 6, 30)


def test_an_examination_cycle_and_a_target_date_may_be_set_together(repository):
    summary = SetStudyGoal(repository)(make_request(target_date=date(2027, 2, 6)))

    assert summary.examination is not None
    assert summary.target_date == date(2027, 2, 6)


def test_a_goal_aiming_at_nothing_is_refused(repository):
    with pytest.raises(MissingGoalTargetError):
        SetStudyGoal(repository)(make_request(examination_cycle_label=None))

    assert repository.goals == {}
    assert repository.learners == {}


def test_an_unknown_learning_program_is_refused(repository):
    with pytest.raises(CurriculumNotAvailableError) as excinfo:
        SetStudyGoal(repository)(make_request(program_code="gate-ee"))

    assert "seed_curriculum" in str(excinfo.value)


def test_a_program_with_no_active_curriculum_version_is_refused(repository):
    repository.active_versions.clear()

    with pytest.raises(CurriculumNotAvailableError) as excinfo:
        SetStudyGoal(repository)(make_request())

    assert "active curriculum version" in str(excinfo.value)


def test_an_unknown_examination_cycle_is_refused(repository):
    with pytest.raises(ExaminationScheduleNotFoundError) as excinfo:
        SetStudyGoal(repository)(make_request(examination_cycle_label="2030"))

    assert "seed_examination_schedule" in str(excinfo.value)
    assert repository.goals == {}


def test_more_than_one_stored_learner_is_refused(repository):
    """ "The local learner" is undefined then, and guessing would misattach the goal."""
    set_goal = SetStudyGoal(repository)
    set_goal(make_request())
    stored = next(iter(repository.learners.values()))
    repository.add_learner(type(stored)(id=uuid.uuid4(), display_name="Second", timezone=TIMEZONE))

    with pytest.raises(AmbiguousLearnerError):
        set_goal(make_request())


def test_a_schedule_with_no_examination_period_reports_no_window():
    """The seed refuses to create one, but a hand-edited database could hold it."""
    repository = FakeStudyGoalRepository(
        learning_programs={PROGRAM_CODE: PROGRAM_ID},
        active_versions={PROGRAM_ID: CurriculumVersionSummary(id=VERSION_ID, version_label="2027")},
        schedules=(make_schedule(),),
        periods=(
            ExaminationPeriodRecord(
                id=uuid.uuid4(),
                examination_schedule_id=SCHEDULE_ID,
                period_type="registration",
                starts_on=date(2026, 8, 14),
                ends_on=date(2026, 9, 21),
            ),
        ),
    )

    summary = SetStudyGoal(repository)(make_request())

    assert summary.examination is not None
    assert summary.examination.window_starts_on is None
    assert summary.examination.window_ends_on is None
