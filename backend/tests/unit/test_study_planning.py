"""Tests for the deterministic planning rules.

These need no database, no clock, and no request: the rules are pure functions
over plain values, which is the property that makes a plan replayable and
explainable rather than merely produced.
"""

import uuid
from datetime import date

import pytest

from app.domain.study_planning import (
    DatedItem,
    DayCapacity,
    PlannableTopic,
    SyllabusPosition,
    assess_horizon_coverage,
    order_by_prerequisites,
    order_by_syllabus,
    schedule_sessions,
    select_overdue,
)

MONDAY = date(2026, 8, 10)


def plannable(subject: int, *path: int) -> PlannableTopic:
    """A topic at a stated place in the syllabus, with an identity of its own."""
    return PlannableTopic(
        topic_id=uuid.uuid4(),
        position=SyllabusPosition(subject_position=subject, path=path, topic_id=uuid.uuid4()),
    )


def days(*minutes: int) -> tuple[DayCapacity, ...]:
    """Consecutive days from a Monday, each holding the minutes given."""
    return tuple(
        DayCapacity(on=date.fromordinal(MONDAY.toordinal() + offset), available_minutes=available)
        for offset, available in enumerate(minutes)
    )


# -- ordering ---------------------------------------------------------------


def test_syllabus_order_follows_subject_then_position():
    first_subject_first = plannable(1, 1)
    first_subject_second = plannable(1, 2)
    second_subject = plannable(2, 1)

    ordered = order_by_syllabus([second_subject, first_subject_second, first_subject_first])

    assert ordered.topics == (first_subject_first, first_subject_second, second_subject)


def test_syllabus_order_places_a_parent_before_its_own_children():
    """A branch is walked whole: the parent, then everything beneath it, then the
    next branch. Sorting on the last position alone would interleave them."""
    parent = plannable(1, 1)
    child = plannable(1, 1, 1)
    next_branch = plannable(1, 2)

    ordered = order_by_syllabus([next_branch, child, parent])

    assert ordered.topics == (parent, child, next_branch)


def test_syllabus_order_applies_no_prerequisites():
    ordered = order_by_syllabus([plannable(1, 1)])

    assert ordered.prerequisites_applied == 0
    assert ordered.held_back_by_a_cycle == ()


def test_prerequisite_order_puts_a_topic_after_what_it_depends_on():
    early = plannable(1, 1)
    late = plannable(1, 2)

    ordered = order_by_prerequisites([early, late], {early.topic_id: frozenset({late.topic_id})})

    assert ordered.topics == (late, early)
    assert ordered.prerequisites_applied == 1


def test_prerequisite_order_without_any_links_is_syllabus_order():
    """The curated GATE CSE curriculum stores no prerequisite edge, so this is
    what a learner choosing `prerequisites_first` actually receives today. The
    count is what lets the plan say so instead of implying an order it did not
    follow."""
    topics = [plannable(1, 2), plannable(1, 1), plannable(2, 1)]

    ordered = order_by_prerequisites(topics, {})

    assert ordered.topics == order_by_syllabus(topics).topics
    assert ordered.prerequisites_applied == 0


def test_prerequisite_order_breaks_ties_by_syllabus_position():
    """Two topics ready at the same moment are a choice, and the choice is fixed:
    without a tie-break the same curriculum could produce different plans."""
    first = plannable(1, 1)
    second = plannable(1, 2)
    third = plannable(1, 3)

    ordered = order_by_prerequisites(
        [third, second, first], {third.topic_id: frozenset({first.topic_id})}
    )

    assert ordered.topics == (first, second, third)


def test_prerequisite_order_ignores_a_link_to_a_topic_it_is_not_planning():
    """A prerequisite that is a grouping heading, or belongs to another version,
    cannot hold anything back — it is not work the plan contains."""
    topic = plannable(1, 1)

    ordered = order_by_prerequisites([topic], {topic.topic_id: frozenset({uuid.uuid4()})})

    assert ordered.topics == (topic,)
    assert ordered.prerequisites_applied == 0


def test_a_loop_of_prerequisites_holds_topics_back_rather_than_dropping_them():
    """A plan that silently omitted a topic would be worse than one admitting it
    could not order it, so the unplaceable topics are appended and counted."""
    first = plannable(1, 1)
    second = plannable(1, 2)
    free = plannable(1, 3)

    ordered = order_by_prerequisites(
        [first, second, free],
        {
            first.topic_id: frozenset({second.topic_id}),
            second.topic_id: frozenset({first.topic_id}),
        },
    )

    assert ordered.topics == (free, first, second)
    assert ordered.held_back_by_a_cycle == (first, second)


def test_a_topic_that_is_its_own_prerequisite_is_still_planned():
    topic = plannable(1, 1)

    ordered = order_by_prerequisites([topic], {topic.topic_id: frozenset({topic.topic_id})})

    assert ordered.topics == (topic,)
    assert ordered.held_back_by_a_cycle == ()


def test_ordering_returns_every_topic_exactly_once():
    topics = [plannable(1, index) for index in range(1, 6)]

    ordered = order_by_prerequisites(
        topics,
        {topics[0].topic_id: frozenset({topics[4].topic_id})},
    )

    assert sorted(topic.topic_id for topic in ordered.topics) == sorted(
        topic.topic_id for topic in topics
    )


# -- scheduling -------------------------------------------------------------


def test_a_day_is_filled_with_whole_sessions():
    topics = [uuid.uuid4() for _ in range(3)]

    sessions = schedule_sessions(topics, days(120), session_minutes=60)

    assert [session.estimated_minutes for session in sessions] == [60, 60]
    assert {session.scheduled_for for session in sessions} == {MONDAY}


def test_time_left_over_after_a_whole_session_is_not_used():
    """A learner with two and a half hours gets two sessions, not two and an
    offcut too short to study."""
    topics = [uuid.uuid4() for _ in range(3)]

    sessions = schedule_sessions(topics, days(150), session_minutes=60)

    assert [session.estimated_minutes for session in sessions] == [60, 60]


def test_a_day_shorter_than_one_session_still_gets_a_topic():
    """A learner with thirty minutes a day is planning, not failing, so the day
    gets one shorter session rather than nothing."""
    sessions = schedule_sessions([uuid.uuid4()], days(30), session_minutes=60)

    assert [session.estimated_minutes for session in sessions] == [30]


def test_a_day_with_no_time_gets_nothing():
    """Zero minutes is a day kept free and a day never set alike: neither is a
    statement that the learner can study."""
    sessions = schedule_sessions([uuid.uuid4()], days(0), session_minutes=60)

    assert sessions == ()


def test_work_carries_on_to_the_next_day_with_time():
    topics = [uuid.uuid4() for _ in range(3)]

    sessions = schedule_sessions(topics, days(60, 0, 60), session_minutes=60)

    assert [session.scheduled_for for session in sessions] == [
        MONDAY,
        date.fromordinal(MONDAY.toordinal() + 2),
    ]


def test_topics_are_placed_in_the_order_given():
    topics = [uuid.uuid4() for _ in range(3)]

    sessions = schedule_sessions(topics, days(180), session_minutes=60)

    assert [session.topic_id for session in sessions] == topics


def test_scheduling_stops_when_the_topics_run_out():
    sessions = schedule_sessions([uuid.uuid4()], days(600, 600), session_minutes=60)

    assert len(sessions) == 1


def test_no_topic_is_scheduled_twice_in_a_long_week():
    topics = [uuid.uuid4() for _ in range(4)]

    sessions = schedule_sessions(topics, days(600, 600, 600), session_minutes=60)

    assert len({session.topic_id for session in sessions}) == len(sessions)


def test_a_week_with_no_capacity_schedules_nothing():
    sessions = schedule_sessions([uuid.uuid4()], days(0, 0, 0, 0, 0, 0, 0), session_minutes=60)

    assert sessions == ()


def test_scheduling_the_same_inputs_twice_gives_the_same_plan():
    """The property the whole feature rests on: a plan is reproducible, so it can
    be explained and re-derived rather than merely trusted."""
    topics = [uuid.uuid4() for _ in range(5)]
    capacities = days(90, 0, 120, 45, 60, 0, 0)

    first = schedule_sessions(topics, capacities, session_minutes=60)
    second = schedule_sessions(topics, capacities, session_minutes=60)

    assert first == second


def test_a_session_must_have_a_positive_length():
    with pytest.raises(ValueError):
        schedule_sessions([uuid.uuid4()], days(60), session_minutes=0)


# -- overdue items ----------------------------------------------------------


def dated(scheduled_for, is_settled=False, item_id=None):
    return DatedItem(
        plan_item_id=item_id or uuid.uuid4(), scheduled_for=scheduled_for, is_settled=is_settled
    )


def test_an_item_dated_before_today_with_work_undone_is_overdue():
    item = dated(date(2026, 8, 7))

    assert select_overdue([item], date(2026, 8, 9)) == (item.plan_item_id,)


def test_an_item_dated_today_is_not_overdue():
    """The day has not finished. Adapting in the morning must not declare it lost."""
    assert select_overdue([dated(date(2026, 8, 9))], date(2026, 8, 9)) == ()


def test_an_item_dated_after_today_is_not_overdue():
    assert select_overdue([dated(date(2026, 8, 10))], date(2026, 8, 9)) == ()


def test_an_undated_item_is_never_overdue():
    """A roadmap item says what order to work in, not which day; it cannot be
    late for a day it never named."""
    assert select_overdue([dated(None)], date(2026, 8, 9)) == ()


def test_settled_work_is_never_overdue_however_late_the_day_it_was_placed_on():
    """Completed, skipped, and postponed work alike. Something has already been
    said about it, so nothing carries it forward on the learner's behalf."""
    assert select_overdue([dated(date(2020, 1, 1), is_settled=True)], date(2026, 8, 9)) == ()


def test_an_unsettled_item_among_settled_ones_is_the_only_one_overdue():
    """The boundary is per item, so a day holding both does not settle as a whole."""
    settled = dated(date(2026, 8, 1), is_settled=True)
    outstanding = dated(date(2026, 8, 1))

    assert select_overdue([settled, outstanding], date(2026, 8, 9)) == (outstanding.plan_item_id,)


def test_the_order_given_is_the_order_returned():
    """A caller writing these back does so deterministically."""
    first, second, third = (dated(date(2026, 8, 1)) for _ in range(3))

    overdue = select_overdue([first, second, third], date(2026, 8, 9))

    assert overdue == (first.plan_item_id, second.plan_item_id, third.plan_item_id)


def test_nothing_overdue_is_an_empty_result_rather_than_a_failure():
    assert select_overdue([], date(2026, 8, 9)) == ()


# --- Horizon coverage: whether a saved week reaches the goal's date -----------
#
# The rule behind FR-004's third acceptance criterion. Every assertion below is
# on a count or a duration; none is on a ratio, because a denominator invites the
# comparison docs/domain/terminology.md rules out.

WEEK_OF_ONE_HOUR_EVERY_DAY = (60,) * 7
WEEK_KEPT_ENTIRELY_FREE = (0,) * 7


def coverage(
    *,
    remaining_topics: int = 10,
    session_minutes: int = 60,
    weekly_minutes: tuple[int, ...] = WEEK_OF_ONE_HOUR_EVERY_DAY,
    starts_on: date = MONDAY,
    ends_on: date | None = None,
):
    """A coverage assessment with one thing varied at a time."""
    return assess_horizon_coverage(
        remaining_topics=remaining_topics,
        session_minutes=session_minutes,
        weekly_minutes=weekly_minutes,
        starts_on=starts_on,
        ends_on=ends_on if ends_on is not None else date(2026, 8, 16),
    )


def test_a_span_counts_both_of_its_ends():
    """Today can still be studied, and so can the day the horizon names."""
    result = coverage(starts_on=MONDAY, ends_on=MONDAY)

    assert result.study_days == 1
    assert result.available_minutes == 60


def test_a_full_week_offers_every_day_it_names():
    result = coverage(starts_on=MONDAY, ends_on=date(2026, 8, 16))

    assert result.study_days == 7
    assert result.available_minutes == 420


def test_only_the_days_a_learner_saved_offer_time():
    """Monday to Friday at 30 minutes; the weekend is not set and offers nothing."""
    weekdays_only = (30, 30, 30, 30, 30, 0, 0)

    result = coverage(weekly_minutes=weekdays_only, starts_on=MONDAY, ends_on=date(2026, 8, 16))

    assert result.available_minutes == 150


def test_a_partial_week_counts_only_the_weekdays_it_reaches():
    """Monday to Wednesday, so Thursday's and the weekend's minutes never count."""
    distinct = (10, 20, 40, 80, 160, 320, 640)

    result = coverage(weekly_minutes=distinct, starts_on=MONDAY, ends_on=date(2026, 8, 12))

    assert result.study_days == 3
    assert result.available_minutes == 70


def test_a_span_starting_midweek_counts_from_that_day():
    """Starting Thursday for four days reaches Thursday to Sunday, not Monday."""
    distinct = (10, 20, 40, 80, 160, 320, 640)

    result = coverage(
        weekly_minutes=distinct, starts_on=date(2026, 8, 13), ends_on=date(2026, 8, 16)
    )

    assert result.study_days == 4
    assert result.available_minutes == 80 + 160 + 320 + 640


def test_counting_by_weekday_agrees_with_walking_the_days():
    """The shortcut is the same sum in a different order, over a long horizon.

    Asserted rather than argued, because an unbounded loop is exactly what the
    weekday count replaces and a drift between them would be invisible.
    """
    distinct = (10, 20, 40, 80, 160, 320, 640)
    starts_on = date(2026, 8, 13)
    ends_on = date(2027, 2, 6)

    walked = sum(
        distinct[date.fromordinal(ordinal).weekday()]
        for ordinal in range(starts_on.toordinal(), ends_on.toordinal() + 1)
    )

    assert (
        coverage(weekly_minutes=distinct, starts_on=starts_on, ends_on=ends_on).available_minutes
        == walked
    )


def test_a_horizon_that_has_passed_offers_no_days_rather_than_negative_ones():
    result = coverage(starts_on=MONDAY, ends_on=date(2026, 8, 9))

    assert result.study_days == 0
    assert result.available_minutes == 0
    assert result.is_sufficient is False


def test_a_week_kept_entirely_free_offers_no_time():
    """Zero minutes is a real answer, not a missing one -- the caller keeps that apart."""
    result = coverage(weekly_minutes=WEEK_KEPT_ENTIRELY_FREE)

    assert result.available_minutes == 0
    assert result.coverable_topics == 0
    assert result.is_sufficient is False


def test_work_needs_one_session_for_each_topic_remaining():
    result = coverage(remaining_topics=12, session_minutes=45)

    assert result.required_minutes == 540


def test_enough_time_is_sufficient_and_short_by_nothing():
    result = coverage(
        remaining_topics=7, session_minutes=60, starts_on=MONDAY, ends_on=date(2026, 8, 16)
    )

    assert result.is_sufficient is True
    assert result.shortfall_minutes == 0
    assert result.coverable_topics == 7


def test_time_exactly_meeting_the_work_is_sufficient():
    """The boundary is decided rather than discovered: meeting is enough."""
    result = coverage(
        remaining_topics=7, session_minutes=60, starts_on=MONDAY, ends_on=date(2026, 8, 16)
    )

    assert result.available_minutes == result.required_minutes
    assert result.is_sufficient is True


def test_too_little_time_reports_the_shortfall_as_a_duration():
    result = coverage(
        remaining_topics=10, session_minutes=60, starts_on=MONDAY, ends_on=date(2026, 8, 16)
    )

    assert result.is_sufficient is False
    assert result.required_minutes == 600
    assert result.available_minutes == 420
    assert result.shortfall_minutes == 180


def test_a_surplus_is_never_reported_as_a_negative_shortfall():
    """A spare three hours and a missing three hours must not share a number."""
    result = coverage(remaining_topics=1, session_minutes=60)

    assert result.is_sufficient is True
    assert result.shortfall_minutes == 0


def test_coverable_topics_floors_rather_than_rounding():
    """Time for half a session is not a topic covered."""
    result = coverage(
        remaining_topics=10,
        session_minutes=60,
        weekly_minutes=(90,) + (0,) * 6,
        starts_on=MONDAY,
        ends_on=MONDAY,
    )

    assert result.available_minutes == 90
    assert result.coverable_topics == 1


def test_coverable_topics_never_exceeds_what_was_asked_about():
    result = coverage(
        remaining_topics=2, session_minutes=60, starts_on=MONDAY, ends_on=date(2026, 8, 16)
    )

    assert result.available_minutes == 420
    assert result.coverable_topics == 2


def test_a_plan_with_nothing_left_needs_no_time():
    result = coverage(remaining_topics=0)

    assert result.required_minutes == 0
    assert result.coverable_topics == 0
    assert result.is_sufficient is True


def test_the_same_inputs_give_the_same_assessment():
    assert coverage() == coverage()


def test_coverage_requires_a_session_of_positive_length():
    with pytest.raises(ValueError):
        coverage(session_minutes=0)


def test_topics_remaining_cannot_be_negative():
    with pytest.raises(ValueError):
        coverage(remaining_topics=-1)


def test_a_week_must_describe_exactly_seven_days():
    with pytest.raises(ValueError):
        coverage(weekly_minutes=(60, 60, 60))
