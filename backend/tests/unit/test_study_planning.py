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


def dated(scheduled_for, is_done=False, item_id=None):
    return DatedItem(
        plan_item_id=item_id or uuid.uuid4(), scheduled_for=scheduled_for, is_done=is_done
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


def test_completed_work_is_never_overdue_however_late_it_was_done():
    assert select_overdue([dated(date(2020, 1, 1), is_done=True)], date(2026, 8, 9)) == ()


def test_the_order_given_is_the_order_returned():
    """A caller writing these back does so deterministically."""
    first, second, third = (dated(date(2026, 8, 1)) for _ in range(3))

    overdue = select_overdue([first, second, third], date(2026, 8, 9))

    assert overdue == (first.plan_item_id, second.plan_item_id, third.plan_item_id)


def test_nothing_overdue_is_an_empty_result_rather_than_a_failure():
    assert select_overdue([], date(2026, 8, 9)) == ()
