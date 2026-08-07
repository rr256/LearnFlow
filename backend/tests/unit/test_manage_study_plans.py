"""Tests for generating and reading a learner's study plans.

Every port is a fake and the clock is fixed, so each assertion is about a rule
rather than about a database or the day the suite happens to run.
"""

import uuid
from datetime import UTC, date, datetime

import pytest

from app.application.dto.availability import WEEKDAYS
from app.application.dto.planning_preferences import PlanningPreferences
from app.application.dto.study_plan import (
    ACTIVE,
    DEFAULT_SESSION_MINUTES,
    ROADMAP,
    SUPERSEDED,
    WEEKLY,
    PlanGenerationRequest,
    StudyPlanFilters,
)
from app.application.ports.curriculum_seed_repository import TopicRelationshipRecord
from app.application.ports.study_goal_repository import StudyGoalRecord
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_study_plans import (
    LearnerNotSetUpError,
    StudyGoalNotFoundError,
    StudyPlanIntegrityError,
    StudyPlanNotFoundError,
    UnknownPlanFilterError,
)
from tests.unit.fake_learner_repository import learner
from tests.unit.fake_topic_progress_repository import progress
from tests.unit.planning_fixtures import TODAY, Planning
from tests.unit.schedule_fixtures import gate_2027_periods


def roadmap(generated):
    return next(plan for plan in generated.plans if plan.plan_type == ROADMAP)


def weekly(generated):
    return next(plan for plan in generated.plans if plan.plan_type == WEEKLY)


# -- what a plan contains ---------------------------------------------------


def test_a_learner_with_no_progress_still_receives_a_plan():
    """FR-002's last acceptance criterion, stated as a test."""
    generated = Planning(availability={"thursday": 120}).generate()

    assert [plan.plan_type for plan in generated.plans] == [ROADMAP, WEEKLY]
    assert roadmap(generated).item_count == 3


def test_only_trackable_topics_are_planned():
    """A topic that groups subtopics is a heading rather than work, the rule
    PRG-004 applies when it refuses a stage against one."""
    planning = Planning()

    generated = planning.generate()

    planned = {item.topic.id for item in roadmap(generated).items}
    assert planning.grouping.id not in planned
    assert planned == {planning.logic.id, planning.sets.id, planning.scheduling.id}


def test_the_roadmap_follows_syllabus_order():
    planning = Planning()

    items = roadmap(planning.generate()).items

    assert [item.topic.id for item in items] == [
        planning.logic.id,
        planning.sets.id,
        planning.scheduling.id,
    ]
    assert [item.priority for item in items] == [1, 2, 3]


def test_a_roadmap_item_carries_no_date():
    """A roadmap says what order to work in, not which day to do it on."""
    items = roadmap(Planning(availability={"thursday": 120}).generate()).items

    assert all(item.scheduled_for is None for item in items)


def test_the_roadmap_runs_from_today_to_the_examination_window():
    generated = Planning().generate()

    plan = roadmap(generated)
    assert plan.period_start == TODAY
    assert plan.period_end == min(
        record.starts_on
        for record in gate_2027_periods(uuid.uuid4())
        if record.period_type == "examination"
    )


def test_the_horizon_is_whichever_of_the_two_comes_first():
    """A goal aiming at both is planned against the binding constraint; planning
    against the later date would quietly overrun the earlier."""
    generated = Planning(target_date=date(2026, 12, 1)).generate()

    assert roadmap(generated).period_end == date(2026, 12, 1)


def test_a_goal_aiming_at_a_target_date_alone_plans_to_that_date():
    generated = Planning(aims_at_examination=False, target_date=date(2027, 1, 5)).generate()

    plan = roadmap(generated)
    assert plan.period_end == date(2027, 1, 5)
    assert "target date" in plan.generation_reason


def test_every_item_explains_itself():
    """FR-003: the learner can see why an item is recommended."""
    items = roadmap(Planning().generate()).items

    assert all(item.recommendation_reason for item in items)
    assert "Engineering Mathematics" in items[0].recommendation_reason
    assert "1 of 3" in items[0].recommendation_reason


def test_an_item_names_a_stage_the_learner_recorded():
    planning = Planning()
    planning.progress.records = [
        progress(
            learner_id=planning.learner.id,
            topic_id=planning.sets.id,
            learning_stage="developing_confidence",
        )
    ]

    items = roadmap(planning.generate()).items

    assert "Developing confidence" in items[1].recommendation_reason
    assert "recorded" not in items[0].recommendation_reason


def test_a_recorded_stage_does_not_reorder_the_plan():
    """A stage guides the next action rather than scoring a topic (FR-005), and
    nothing here ranks one topic above another."""
    planning = Planning()
    planning.progress.records = [
        progress(
            learner_id=planning.learner.id,
            topic_id=planning.scheduling.id,
            learning_stage="strong_understanding",
        )
    ]

    items = roadmap(planning.generate()).items

    assert [item.topic.id for item in items] == [
        planning.logic.id,
        planning.sets.id,
        planning.scheduling.id,
    ]


# -- the week ---------------------------------------------------------------


def test_the_week_places_topics_on_the_days_the_learner_can_study():
    planning = Planning(availability={"thursday": 120, "saturday": 60})

    items = weekly(planning.generate()).items

    assert [item.scheduled_for for item in items] == [
        date(2026, 8, 6),
        date(2026, 8, 6),
        date(2026, 8, 8),
    ]


def test_a_day_the_learner_has_not_set_holds_no_work():
    """The planner declines to invent a week nobody described."""
    planning = Planning(availability={"thursday": 60})

    items = weekly(planning.generate()).items

    assert [item.scheduled_for for item in items] == [date(2026, 8, 6)]


def test_a_day_kept_free_holds_no_work_either():
    planning = Planning(availability={"thursday": 60, "friday": 0})

    items = weekly(planning.generate()).items

    assert [item.scheduled_for for item in items] == [date(2026, 8, 6)]


def test_a_week_maps_each_date_to_the_day_the_learner_named():
    """The one place a calendar date meets a stored day name. Getting it wrong
    shifts a learner's whole week with no error anywhere (ADR-018), so every day
    is checked rather than one."""
    for offset, day in enumerate(WEEKDAYS):
        monday = date(2026, 8, 10)
        planning = Planning(
            availability={day: 60},
            instant=datetime(2026, 8, 10, 9, 0, tzinfo=UTC),
        )

        items = weekly(planning.generate()).items

        assert [item.scheduled_for for item in items] == [
            date.fromordinal(monday.toordinal() + offset)
        ], f"{day} was not placed on the right date"


def test_no_week_is_written_when_no_availability_is_saved():
    generated = Planning().generate()

    assert [plan.plan_type for plan in generated.plans] == [ROADMAP]
    assert "no day-by-day plan was built" in roadmap(generated).generation_reason
    assert "Save your study week" in roadmap(generated).generation_reason


def test_no_week_is_written_when_the_saved_week_is_entirely_free():
    generated = Planning(availability={"thursday": 0, "friday": 0}).generate()

    assert [plan.plan_type for plan in generated.plans] == [ROADMAP]


def test_the_week_covers_seven_days_from_today():
    generated = Planning(availability={"thursday": 60}).generate()

    plan = weekly(generated)
    assert plan.period_start == TODAY
    assert plan.period_end == date(2026, 8, 12)


# -- session length ---------------------------------------------------------


def test_the_learner_s_session_length_is_used():
    planning = Planning(
        preferences=PlanningPreferences(preferred_session_minutes=90),
        availability={"thursday": 180},
    )

    generated = planning.generate()

    assert all(item.estimated_minutes == 90 for item in weekly(generated).items)
    assert "90 minutes, the length you prefer" in roadmap(generated).generation_reason


def test_an_unset_session_length_is_chosen_by_the_planner_and_said_so():
    """Nothing is stored against the goal either way: a preference nobody set
    must not read as one somebody chose (ADR-019)."""
    generated = Planning(availability={"thursday": 120}).generate()

    assert all(
        item.estimated_minutes == DEFAULT_SESSION_MINUTES for item in weekly(generated).items
    )
    assert "LearnFlow chose" in roadmap(generated).generation_reason


def test_a_day_shorter_than_a_session_still_gets_one_topic():
    planning = Planning(
        preferences=PlanningPreferences(preferred_session_minutes=60),
        availability={"thursday": 30},
    )

    items = weekly(planning.generate()).items

    assert [item.estimated_minutes for item in items] == [30]


# -- topic order ------------------------------------------------------------


def test_prerequisites_first_reorders_when_links_are_stored():
    """`logic` sits first in the syllabus but depends on `scheduling`, so it moves
    behind it. Everything ready at each step is taken in syllabus order, which is
    what makes one valid topological order the defined one."""
    planning = Planning(preferences=PlanningPreferences(topic_sequencing="prerequisites_first"))
    planning.curriculum.relationships = [
        TopicRelationshipRecord(
            source_topic_id=planning.scheduling.id,
            target_topic_id=planning.logic.id,
            relationship_type="prerequisite",
        )
    ]

    generated = planning.generate()

    assert [item.topic.id for item in roadmap(generated).items] == [
        planning.sets.id,
        planning.scheduling.id,
        planning.logic.id,
    ]
    assert "prerequisites first" in roadmap(generated).generation_reason


def test_prerequisites_first_falls_back_to_syllabus_order_and_says_so():
    """The curated GATE CSE curriculum stores no prerequisite edge, so this is
    what a learner choosing that order actually receives. A plan claiming an
    order it did not follow would be worse than one admitting the fallback."""
    planning = Planning(preferences=PlanningPreferences(topic_sequencing="prerequisites_first"))

    generated = planning.generate()

    plan = roadmap(generated)
    assert [item.topic.id for item in plan.items] == [
        planning.logic.id,
        planning.sets.id,
        planning.scheduling.id,
    ]
    assert "syllabus order" in plan.generation_reason
    assert "syllabus order" in plan.items[0].recommendation_reason


def test_a_recommended_before_link_does_not_constrain_the_order():
    """A recommendation is not a constraint, and a plan treating one as a
    constraint could not explain the difference."""
    planning = Planning(preferences=PlanningPreferences(topic_sequencing="prerequisites_first"))
    planning.curriculum.relationships = [
        TopicRelationshipRecord(
            source_topic_id=planning.scheduling.id,
            target_topic_id=planning.logic.id,
            relationship_type="recommended_before",
        )
    ]

    items = roadmap(planning.generate()).items

    assert items[0].topic.id == planning.logic.id


# -- regeneration -----------------------------------------------------------


def test_generating_again_supersedes_the_previous_plans():
    planning = Planning(availability={"thursday": 60})
    first = planning.generate()

    second = planning.generate()

    assert set(second.superseded_plan_ids) == {plan.id for plan in first.plans}
    stored = {plan.id: plan.status for plan in planning.plans.plans}
    assert all(stored[plan.id] == SUPERSEDED for plan in first.plans)
    assert all(stored[plan.id] == ACTIVE for plan in second.plans)


def test_generating_again_keeps_the_earlier_plan_rather_than_deleting_it():
    planning = Planning(availability={"thursday": 60})
    first = planning.generate()

    planning.generate()

    assert planning.planner().read(roadmap(first).id).status == SUPERSEDED


def test_a_superseded_plan_keeps_the_reason_it_was_written_with():
    planning = Planning(availability={"thursday": 60})
    first = roadmap(planning.generate())

    planning.generate()

    assert planning.planner().read(first.id).generation_reason == first.generation_reason


def test_the_same_inputs_generate_the_same_plan():
    """The property the feature rests on. Identifiers differ between runs; the
    recommendations do not."""
    first = Planning(availability={"thursday": 120}).generate()
    second = Planning(availability={"thursday": 120}).generate()

    def shape(generated):
        return [
            (
                plan.plan_type,
                plan.period_start,
                plan.generation_reason,
                [
                    (item.priority, item.scheduled_for, item.estimated_minutes)
                    for item in plan.items
                ],
            )
            for plan in generated.plans
        ]

    assert shape(first) == shape(second)


# -- reading ----------------------------------------------------------------


def test_a_plan_reads_back_with_its_items_in_plan_order():
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()

    plan = planning.planner().read(roadmap(generated).id)

    assert [item.priority for item in plan.items] == [1, 2, 3]
    assert plan.item_count == 3


def test_a_listed_plan_reports_its_size_without_its_items():
    planning = Planning(availability={"thursday": 120})
    planning.generate()

    page = planning.planner().list_study_plans(filters=StudyPlanFilters(), limit=25, offset=0)

    assert page.total == 2
    assert all(plan.items == () for plan in page.plans)
    assert sorted(plan.item_count for plan in page.plans) == [2, 3]


def test_plans_can_be_filtered_by_goal_type_and_status():
    planning = Planning(availability={"thursday": 120})
    planning.generate()

    page = planning.planner().list_study_plans(
        filters=StudyPlanFilters(study_goal_id=planning.goal.id, plan_type=ROADMAP, status=ACTIVE),
        limit=25,
        offset=0,
    )

    assert [plan.plan_type for plan in page.plans] == [ROADMAP]


def test_a_goal_filter_matching_nothing_is_an_empty_page():
    planning = Planning(availability={"thursday": 120})
    planning.generate()

    page = planning.planner().list_study_plans(
        filters=StudyPlanFilters(study_goal_id=uuid.uuid4()), limit=25, offset=0
    )

    assert page.plans == ()
    assert page.total == 0


def test_an_unknown_plan_type_filter_is_refused():
    with pytest.raises(UnknownPlanFilterError) as raised:
        Planning().planner().list_study_plans(
            filters=StudyPlanFilters(plan_type="fortnightly"), limit=25, offset=0
        )

    assert raised.value.field == "plan_type"


def test_an_unknown_status_filter_is_refused():
    with pytest.raises(UnknownPlanFilterError) as raised:
        Planning().planner().list_study_plans(
            filters=StudyPlanFilters(status="finished"), limit=25, offset=0
        )

    assert raised.value.field == "status"


def test_a_learner_who_does_not_exist_yet_has_no_plans():
    planning = Planning()
    planning.learners.learners = []

    page = planning.planner().list_study_plans(filters=StudyPlanFilters(), limit=25, offset=0)

    assert page.plans == ()
    assert page.total == 0


# -- refusals ---------------------------------------------------------------


def test_generating_without_a_learner_is_refused():
    planning = Planning()
    planning.learners.learners = []

    with pytest.raises(LearnerNotSetUpError):
        planning.generate()


def test_generating_for_another_learner_s_goal_reports_it_as_missing():
    """Saying "that exists but is not yours" would confirm a record the caller
    may not read."""
    planning = Planning()
    planning.goals.goals = [
        StudyGoalRecord(
            id=planning.goal.id,
            learner_id=uuid.uuid4(),
            learning_program_id=planning.program_id,
            curriculum_version_id=planning.version.id,
            examination_schedule_id=planning.schedule.id,
            target_date=None,
            status="active",
            planning_preferences=PlanningPreferences(),
        )
    ]

    with pytest.raises(StudyGoalNotFoundError):
        planning.generate()


def test_generating_for_a_goal_that_is_not_stored_is_refused():
    planning = Planning()

    with pytest.raises(StudyGoalNotFoundError):
        planning.planner().generate(PlanGenerationRequest(study_goal_id=uuid.uuid4()))


def test_generating_against_a_missing_curriculum_version_is_reported():
    planning = Planning()
    planning.goals.versions = ()

    with pytest.raises(StudyPlanIntegrityError):
        planning.generate()


def test_generating_with_more_than_one_learner_stored_is_refused():
    planning = Planning()
    planning.learners.add_learner(learner(display_name="Second"))

    with pytest.raises(AmbiguousLocalLearnerError):
        planning.generate()


def test_reading_another_learner_s_plan_reports_it_as_missing():
    planning = Planning(availability={"thursday": 60})
    generated = planning.generate()
    planning.learners.learners = [learner(display_name="Someone else")]

    with pytest.raises(StudyPlanNotFoundError):
        planning.planner().read(roadmap(generated).id)


def test_reading_a_plan_that_is_not_stored_is_refused():
    with pytest.raises(StudyPlanNotFoundError):
        Planning().planner().read(uuid.uuid4())


# -- the learner's own day --------------------------------------------------


def test_the_plan_starts_on_the_learner_s_date_not_the_server_s():
    """23:00 UTC is already tomorrow in `Asia/Kolkata`. A plan starting yesterday
    because the process is elsewhere would be wrong on its first line."""
    planning = Planning(instant=datetime(2026, 8, 5, 23, 0, tzinfo=UTC))

    generated = planning.generate()

    assert generated.generated_on == date(2026, 8, 6)


def test_an_unreadable_timezone_falls_back_to_utc_rather_than_failing():
    """A plan a day out is recoverable; refusing to plan at all is not."""
    planning = Planning(
        timezone="Mars/Olympus_Mons", instant=datetime(2026, 8, 6, 9, 0, tzinfo=UTC)
    )

    generated = planning.generate()

    assert generated.generated_on == date(2026, 8, 6)
