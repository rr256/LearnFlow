"""Tests for PLN-006 — whether the saved week reaches the goal's horizon.

FR-004's third acceptance criterion, exercised over the use case against fakes
with a fixed clock. The arithmetic itself is tested in
`tests/unit/test_study_planning.py`, where it is pure; what these establish is
everything that needs a record to decide — which topics remain, which gap made a
question unanswerable, and that asking writes nothing.

Every assertion is on a count, a duration, or an absence. None is on a ratio, and
several assert that no wording describes the learner rather than the plan.

The fixture curriculum holds three trackable topics, and the GATE 2027 schedule
opens its examination window on 2027-02-06.
"""

import uuid
from datetime import date

import pytest

from app.application.dto.planning_preferences import PlanningPreferences
from app.application.dto.study_plan import (
    COMPLETED,
    DEFAULT_SESSION_MINUTES,
    POSTPONED,
    ROADMAP,
    SKIPPED,
    PlanItemStatusChange,
)
from app.application.ports.study_goal_repository import StudyGoalRecord
from app.application.use_cases.manage_study_plans import StudyGoalNotFoundError
from tests.unit.planning_fixtures import TODAY, Planning

EVERY_DAY = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def assess(planning: Planning):
    """Generate a plan, then ask whether the saved week reaches the horizon."""
    planning.generate()
    return planning.planner().assess_feasibility(planning.goal.id)


def roadmap_items(planning: Planning):
    """The items of the goal's active roadmap."""
    plan = next(
        plan
        for plan in planning.plans.list_active_study_plans(planning.goal.id)
        if plan.plan_type == ROADMAP
    )
    return planning.plans.list_plan_items(plan.id)


def snapshot(planning: Planning):
    """Every plan and item state, for asserting that a read changed nothing."""
    return [
        (
            plan.id,
            plan.status,
            plan.period_end,
            tuple(
                (item.id, item.status, item.scheduled_for, item.completed_at)
                for item in planning.plans.list_plan_items(plan.id)
            ),
        )
        for plan in planning.plans.list_active_study_plans(planning.goal.id)
    ]


def test_a_generous_week_is_enough_for_the_work_that_remains():
    result = assess(Planning(availability=dict.fromkeys(EVERY_DAY, 120)))

    assert result.verdict == "sufficient"
    assert result.shortfall_minutes == 0
    assert result.remaining_topic_count == 3
    assert result.coverable_topic_count == 3


def test_a_week_that_cannot_reach_the_horizon_reports_the_shortfall_as_a_duration():
    planning = Planning(availability={"thursday": 30}, aims_at_examination=False, target_date=TODAY)

    result = assess(planning)

    assert result.verdict == "insufficient"
    assert result.required_minutes == 3 * DEFAULT_SESSION_MINUTES
    assert result.shortfall_minutes > 0


def test_a_shortfall_names_how_many_topics_the_time_does_cover():
    """The meaningful trade-off FR-004 asks for, stated as two counts.

    Today is a Thursday and so is the target date a week later, so the span holds
    two Thursdays and therefore two hours -- enough for two of the three topics.
    """
    planning = Planning(
        availability={"thursday": 60},
        aims_at_examination=False,
        target_date=date(2026, 8, 13),
    )

    result = assess(planning)

    assert result.verdict == "insufficient"
    assert result.available_minutes == 120
    assert result.remaining_topic_count == 3
    assert result.coverable_topic_count == 2


def test_a_shortfall_names_what_the_learner_could_change():
    planning = Planning(
        availability={"thursday": 60},
        aims_at_examination=False,
        target_date=date(2026, 8, 13),
    )

    reason = assess(planning).reason

    assert "save more study time" in reason
    assert "shorten your sessions" in reason
    assert "later date" in reason


def test_the_horizon_is_the_goals_own_target_date():
    planning = Planning(
        availability={"monday": 60}, aims_at_examination=False, target_date=date(2026, 12, 31)
    )

    assert assess(planning).horizon_ends_on == date(2026, 12, 31)


def test_the_earlier_of_two_horizons_binds():
    """The rule generation applies: whichever date falls first."""
    planning = Planning(availability={"monday": 60}, target_date=date(2026, 9, 1))

    assert assess(planning).horizon_ends_on == date(2026, 9, 1)


def test_a_goal_aiming_at_nothing_cannot_be_assessed():
    planning = Planning(availability={"monday": 60}, aims_at_examination=False)

    result = assess(planning)

    assert result.verdict == "unknown"
    assert result.unknown_reason == "no_horizon"
    assert result.horizon_ends_on is None


def test_a_goal_with_no_saved_week_cannot_be_assessed():
    result = assess(Planning())

    assert result.verdict == "unknown"
    assert result.unknown_reason == "no_availability_saved"


def test_a_week_kept_entirely_free_is_an_answer_rather_than_unknown():
    """ADR-018's distinction: a day kept free is not a day never set."""
    planning = Planning(availability={"monday": 0, "tuesday": 0})

    result = assess(planning)

    assert result.verdict == "insufficient"
    assert result.unknown_reason is None
    assert result.available_minutes == 0


def test_an_unset_session_length_is_named_as_the_planners_own_choice():
    planning = Planning(availability={"monday": 600})

    result = assess(planning)

    assert result.session_minutes == DEFAULT_SESSION_MINUTES
    assert result.session_minutes_chosen_by_planner is True
    assert "LearnFlow chose" in result.reason


def test_a_session_length_the_learner_set_is_named_as_theirs():
    planning = Planning(
        availability={"monday": 600},
        preferences=PlanningPreferences(preferred_session_minutes=30),
    )

    result = assess(planning)

    assert result.session_minutes == 30
    assert result.session_minutes_chosen_by_planner is False
    assert "that you set" in result.reason


def test_a_completed_topic_is_not_counted_as_remaining():
    """The same exclusion adaptation applies, so the two cannot disagree."""
    planning = Planning(availability={"monday": 600})
    planning.generate()
    item = next(item for item in roadmap_items(planning) if item.topic_id is not None)
    planning.planner().record_item_status(item.id, PlanItemStatusChange(status=COMPLETED))

    assert planning.planner().assess_feasibility(planning.goal.id).remaining_topic_count == 2


@pytest.mark.parametrize("status", [SKIPPED, POSTPONED])
def test_a_settled_but_unfinished_topic_still_needs_time(status: str):
    """Skipping and postponing settle the item, not the topic (ADR-024, ADR-025)."""
    planning = Planning(availability={"monday": 600})
    planning.generate()
    item = next(item for item in roadmap_items(planning) if item.topic_id is not None)
    planning.planner().record_item_status(item.id, PlanItemStatusChange(status=status))

    assert planning.planner().assess_feasibility(planning.goal.id).remaining_topic_count == 3


def test_a_goal_with_no_plan_has_nothing_to_assess():
    """A plan that does not exist cannot be short of time; PLN-001 makes one."""
    planning = Planning(availability={"monday": 600})

    result = planning.planner().assess_feasibility(planning.goal.id)

    assert result.remaining_topic_count == 0
    assert result.verdict == "sufficient"
    assert "No topics are left to plan" in result.reason


def test_a_horizon_that_has_passed_leaves_no_study_days():
    planning = Planning(
        availability={"monday": 600},
        aims_at_examination=False,
        target_date=date(2026, 8, 1),
    )

    result = assess(planning)

    assert result.study_days == 0
    assert result.verdict == "insufficient"
    assert "has passed" in result.reason


def test_assessing_writes_nothing_at_all():
    """The read-only guarantee, asserted rather than described."""
    planning = Planning(availability={"thursday": 30}, aims_at_examination=False, target_date=TODAY)
    planning.generate()
    before = snapshot(planning)
    slots_before = planning.goals.list_availability_slots([planning.goal.id])
    goal_before = planning.goals.find_study_goal(planning.goal.id)

    planning.planner().assess_feasibility(planning.goal.id)
    planning.planner().assess_feasibility(planning.goal.id)

    assert snapshot(planning) == before
    assert planning.goals.list_availability_slots([planning.goal.id]) == slots_before
    assert planning.goals.find_study_goal(planning.goal.id) == goal_before


def test_assessing_the_same_goal_twice_gives_the_same_answer():
    planning = Planning(availability={"monday": 120})
    planning.generate()

    assert planning.planner().assess_feasibility(planning.goal.id) == (
        planning.planner().assess_feasibility(planning.goal.id)
    )


def test_the_assessment_is_dated_in_the_learners_own_timezone():
    """The instant is fixed, so a different zone can only mean a different date."""
    planning = Planning(availability={"monday": 120}, timezone="Pacific/Kiritimati")

    assert assess(planning).assessed_on == date(2026, 8, 6)


def test_another_learners_goal_is_reported_as_missing():
    planning = Planning(availability={"monday": 120})
    other = StudyGoalRecord(
        id=uuid.uuid4(),
        learner_id=uuid.uuid4(),
        learning_program_id=planning.program_id,
        curriculum_version_id=planning.version.id,
        examination_schedule_id=None,
        target_date=TODAY,
        status="active",
        planning_preferences=PlanningPreferences(),
    )
    planning.goals.goals.append(other)

    with pytest.raises(StudyGoalNotFoundError):
        planning.planner().assess_feasibility(other.id)


def test_an_unknown_goal_is_reported_as_missing():
    planning = Planning(availability={"monday": 120})

    with pytest.raises(StudyGoalNotFoundError):
        planning.planner().assess_feasibility(uuid.uuid4())


def test_no_wording_describes_the_learner_rather_than_the_plan():
    """docs/domain/terminology.md: a week that falls short is arithmetic."""
    planning = Planning(availability={"thursday": 30}, aims_at_examination=False, target_date=TODAY)

    reason = assess(planning).reason.lower()

    for wording in ("behind", "you failed", "effort", "too slow", "unrealistic", "give up"):
        assert wording not in reason


def test_nothing_is_reported_as_a_percentage_or_a_ratio():
    planning = Planning(
        availability={"thursday": 60},
        aims_at_examination=False,
        target_date=date(2026, 8, 13),
    )

    reason = assess(planning).reason

    assert "%" not in reason
    assert "/" not in reason
