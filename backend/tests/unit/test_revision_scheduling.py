"""Tests for the deterministic revision rules.

These need no database, no clock, and no request: the rules are pure functions
over plain values, which is what makes a recommendation replayable and
explainable rather than merely produced.

Every assertion is on a date, an interval, or a selection. None is on a count, a
rank, or a score — nothing in revision scheduling produces one.
"""

import uuid
from datetime import date

import pytest

from app.domain.revision_scheduling import (
    DEFAULT_REVISION_INTERVAL_DAYS,
    REVISION_INTERVAL_DAYS,
    DatedRevision,
    due_on,
    interval_for_stage,
    select_due,
)

FINISHED_ON = date(2026, 8, 13)
TODAY = date(2026, 8, 20)


def dated(day: date, *, settled: bool = False) -> DatedRevision:
    """A revision falling due on a day, with an identity of its own."""
    return DatedRevision(revision_id=uuid.uuid4(), due_on=day, is_settled=settled)


# -- how long a topic waits ---------------------------------------------------


def test_every_approved_stage_has_an_interval():
    """The five stages ADR-017 approves, so none falls through to the default."""
    assert set(REVISION_INTERVAL_DAYS) == {
        "not_explored",
        "building_foundation",
        "developing_confidence",
        "practice_ready",
        "strong_understanding",
    }


def test_a_recorded_stage_decides_the_interval_and_is_named():
    result = interval_for_stage("developing_confidence")

    assert result.days == 10
    assert result.learning_stage == "developing_confidence"
    assert result.chosen_by_scheduler is False


def test_no_recorded_stage_means_the_scheduler_chose_for_itself():
    """A topic with no progress row has no stage, and nothing invents one."""
    result = interval_for_stage(None)

    assert result.days == DEFAULT_REVISION_INTERVAL_DAYS
    assert result.learning_stage is None
    assert result.chosen_by_scheduler is True


def test_a_stage_this_build_does_not_recognise_falls_back_rather_than_failing():
    """A later backend adding a sixth stage must not leave a learner with none."""
    result = interval_for_stage("invented")

    assert result.days == DEFAULT_REVISION_INTERVAL_DAYS
    assert result.chosen_by_scheduler is True


def test_a_more_confident_stage_waits_longer_than_a_newer_one():
    """The supportive next action FR-005 asks for, not a ranking of the learner."""
    building = interval_for_stage("building_foundation").days
    confident = interval_for_stage("developing_confidence").days
    ready = interval_for_stage("practice_ready").days
    strong = interval_for_stage("strong_understanding").days

    assert building < confident < ready < strong


def test_every_interval_is_at_least_a_day():
    """A topic finished this morning is not owed revision this afternoon."""
    for stage in (*REVISION_INTERVAL_DAYS, None, "invented"):
        assert interval_for_stage(stage).days >= 1


# -- when it comes back -------------------------------------------------------


def test_a_due_date_is_the_interval_after_the_work_was_finished():
    assert due_on(FINISHED_ON, interval_for_stage("building_foundation")) == date(2026, 8, 20)


def test_a_longer_interval_lands_further_out():
    assert due_on(FINISHED_ON, interval_for_stage("strong_understanding")) == date(2026, 9, 3)


def test_a_due_date_crosses_a_month_boundary_correctly():
    assert due_on(date(2026, 8, 28), interval_for_stage("practice_ready")) == date(2026, 9, 11)


def test_a_due_date_crosses_a_year_boundary_correctly():
    assert due_on(date(2026, 12, 28), interval_for_stage("building_foundation")) == date(2027, 1, 4)


def test_a_due_date_crosses_a_leap_day_correctly():
    assert due_on(date(2028, 2, 26), interval_for_stage("building_foundation")) == date(2028, 3, 4)


def test_a_due_date_is_always_after_the_work():
    for stage in (*REVISION_INTERVAL_DAYS, None):
        assert due_on(FINISHED_ON, interval_for_stage(stage)) > FINISHED_ON


def test_the_same_inputs_give_the_same_due_date():
    assert due_on(FINISHED_ON, interval_for_stage("practice_ready")) == due_on(
        FINISHED_ON, interval_for_stage("practice_ready")
    )


# -- which revisions are due --------------------------------------------------


def test_a_revision_due_today_is_due():
    """Unlike a plan item dated today, which is not yet behind."""
    revision = dated(TODAY)

    assert select_due([revision], TODAY) == (revision.revision_id,)


def test_a_revision_whose_day_has_passed_is_due():
    revision = dated(date(2026, 8, 14))

    assert select_due([revision], TODAY) == (revision.revision_id,)


def test_a_revision_due_later_is_not_due_yet():
    assert select_due([dated(date(2026, 8, 21))], TODAY) == ()


@pytest.mark.parametrize("settled", [True])
def test_a_settled_revision_is_never_due_however_late_its_day(settled: bool):
    assert select_due([dated(date(2026, 7, 1), settled=settled)], TODAY) == ()


def test_an_unsettled_revision_among_settled_ones_is_the_only_one_due():
    owed = dated(date(2026, 8, 14))
    others = [dated(date(2026, 8, 12), settled=True), dated(date(2026, 8, 13), settled=True)]

    assert select_due([*others, owed], TODAY) == (owed.revision_id,)


def test_the_order_given_is_the_order_returned():
    first, second, third = dated(TODAY), dated(date(2026, 8, 12)), dated(date(2026, 8, 18))

    selected = select_due([first, second, third], TODAY)

    assert selected == (first.revision_id, second.revision_id, third.revision_id)


def test_nothing_due_is_an_empty_result_rather_than_a_failure():
    assert select_due([], TODAY) == ()
