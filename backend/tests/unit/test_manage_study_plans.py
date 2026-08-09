"""Tests for generating, reading, and updating a learner's study plans.

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
    COMPLETED,
    DEFAULT_SESSION_MINUTES,
    PLANNED,
    POSTPONED,
    ROADMAP,
    SUPERSEDED,
    WEEKLY,
    PlanGenerationRequest,
    PlanItemStatusChange,
    StudyPlanFilters,
)
from app.application.ports.curriculum_seed_repository import TopicRelationshipRecord
from app.application.ports.study_goal_repository import StudyGoalRecord
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_study_plans import (
    LearnerNotSetUpError,
    NoActivePlanToAdaptError,
    PlanItemNotFoundError,
    PlanItemNotOnActivePlanError,
    StudyGoalNotFoundError,
    StudyPlanIntegrityError,
    StudyPlanNotFoundError,
    UnknownPlanFilterError,
    UnknownPlanItemStatusError,
)
from tests.unit.fake_learner_repository import learner
from tests.unit.fake_topic_progress_repository import progress
from tests.unit.planning_fixtures import DEFAULT_INSTANT, TODAY, Planning
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


# -- completing a plan item -------------------------------------------------


def test_marking_an_item_completed_records_the_status_and_the_time():
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    item = weekly(generated).items[0]

    updated = planning.planner().record_item_status(item.id, PlanItemStatusChange(status=COMPLETED))

    assert updated.status == COMPLETED
    assert updated.completed_at == DEFAULT_INSTANT


def test_completing_an_item_can_be_undone_and_clears_the_time():
    """A learner who marked the wrong line must be able to put it back. Nothing
    here treats finishing work as a verdict, so nothing here is one-way."""
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    item = weekly(generated).items[0]
    planner = planning.planner()
    planner.record_item_status(item.id, PlanItemStatusChange(status=COMPLETED))

    reverted = planner.record_item_status(item.id, PlanItemStatusChange(status=PLANNED))

    assert reverted.status == PLANNED
    assert reverted.completed_at is None


def test_recording_the_status_an_item_already_holds_writes_nothing():
    """A repeated form submission must not fail on its second attempt."""
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    item = weekly(generated).items[0]
    planner = planning.planner()
    first = planner.record_item_status(item.id, PlanItemStatusChange(status=COMPLETED))

    planning.clock.instant = datetime(2026, 8, 7, 9, 0, tzinfo=UTC)
    again = planner.record_item_status(item.id, PlanItemStatusChange(status=COMPLETED))

    assert again.status == COMPLETED
    assert again.completed_at == first.completed_at


@pytest.mark.parametrize("status", ["skipped", "postponed", "finished", ""])
def test_a_status_this_endpoint_does_not_accept_is_refused(status):
    """`skipped` and `postponed` are approved statuses that nothing writes yet;
    they are refused here rather than stored where nothing reads them."""
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    item = weekly(generated).items[0]

    with pytest.raises(UnknownPlanItemStatusError):
        planning.planner().record_item_status(item.id, PlanItemStatusChange(status=status))


def test_a_refused_status_does_not_name_the_value_it_rejected():
    """docs/api/conventions.md keeps the rejected input out of the envelope."""
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    item = weekly(generated).items[0]

    with pytest.raises(UnknownPlanItemStatusError) as raised:
        planning.planner().record_item_status(
            item.id, PlanItemStatusChange(status="definitely-not-a-status")
        )

    assert "definitely-not-a-status" not in str(raised.value)


def test_completing_one_item_moves_no_other_item():
    """The same topic sits on the roadmap and in the week. Completing the week's
    session says that session happened; it does not decide anything about the
    roadmap, and nothing here infers a link the schema does not store."""
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    session = weekly(generated).items[0]
    planner = planning.planner()

    planner.record_item_status(session.id, PlanItemStatusChange(status=COMPLETED))

    roadmap_items = planner.read(roadmap(generated).id).items
    assert [item.status for item in roadmap_items] == [PLANNED, PLANNED, PLANNED]
    assert all(item.completed_at is None for item in roadmap_items)


def test_completing_an_item_records_no_learning_stage():
    """Rule 4 of the domain model: a plan item records whether planned work
    happened, not that the topic is understood."""
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    item = weekly(generated).items[0]

    planning.planner().record_item_status(item.id, PlanItemStatusChange(status=COMPLETED))

    assert planning.progress.records == []


def test_completing_an_item_leaves_the_plan_and_its_reason_alone():
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    week = weekly(generated)
    item = week.items[0]
    planner = planning.planner()

    planner.record_item_status(item.id, PlanItemStatusChange(status=COMPLETED))

    stored = planner.read(week.id)
    assert stored.status == ACTIVE
    assert stored.generation_reason == week.generation_reason
    completed = next(line for line in stored.items if line.id == item.id)
    assert completed.recommendation_reason == item.recommendation_reason
    assert completed.priority == item.priority
    assert completed.scheduled_for == item.scheduled_for


def test_a_completed_item_reads_back_completed_through_its_plan():
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    week = weekly(generated)
    item = week.items[0]
    planner = planning.planner()

    planner.record_item_status(item.id, PlanItemStatusChange(status=COMPLETED))

    statuses = {line.id: line.status for line in planner.read(week.id).items}
    assert statuses[item.id] == COMPLETED


def test_completing_an_item_on_a_superseded_plan_is_refused():
    """A superseded plan is kept because it reads exactly as it was written.
    Writing into one would change the record whose worth is that it does not."""
    planning = Planning(availability={"thursday": 120})
    first = planning.generate()
    item = weekly(first).items[0]
    planning.generate()

    with pytest.raises(PlanItemNotOnActivePlanError):
        planning.planner().record_item_status(item.id, PlanItemStatusChange(status=COMPLETED))


def test_completing_another_learner_s_item_reports_it_as_missing():
    """Not forbidden: saying "that exists but is not yours" would confirm a
    record the caller may not read."""
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    item = weekly(generated).items[0]
    planning.learners.learners = [learner(display_name="Someone else")]

    with pytest.raises(PlanItemNotFoundError):
        planning.planner().record_item_status(item.id, PlanItemStatusChange(status=COMPLETED))


def test_completing_an_item_that_is_not_stored_is_refused():
    with pytest.raises(PlanItemNotFoundError):
        Planning().planner().record_item_status(
            uuid.uuid4(), PlanItemStatusChange(status=COMPLETED)
        )


def test_completing_an_item_with_no_learner_stored_is_refused():
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    item = weekly(generated).items[0]
    planning.learners.learners = []

    with pytest.raises(LearnerNotSetUpError):
        planning.planner().record_item_status(item.id, PlanItemStatusChange(status=COMPLETED))


def test_completing_an_item_with_more_than_one_learner_stored_is_refused():
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    item = weekly(generated).items[0]
    planning.learners.add_learner(learner(display_name="Second"))

    with pytest.raises(AmbiguousLocalLearnerError):
        planning.planner().record_item_status(item.id, PlanItemStatusChange(status=COMPLETED))


def test_a_status_is_validated_before_the_item_is_looked_up():
    """A caller who has misread the contract is told so, whichever item they
    named -- the order `record_stage` applies to an unknown learning stage."""
    with pytest.raises(UnknownPlanItemStatusError):
        Planning().planner().record_item_status(
            uuid.uuid4(), PlanItemStatusChange(status="skipped")
        )


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


# -- adapting a plan --------------------------------------------------------


def complete(planning, item_id):
    """Mark one item completed through the use case, as PLN-004 does."""
    planning.planner().record_item_status(item_id, PlanItemStatusChange(status=COMPLETED))


def test_adapting_supersedes_the_active_plans_and_writes_a_new_pair():
    planning = Planning(availability={"thursday": 120})
    first = planning.generate()

    adapted = planning.planner().adapt(planning.goal.id)

    assert sorted(adapted.superseded_plan_ids) == sorted(plan.id for plan in first.plans)
    assert [plan.plan_type for plan in adapted.plans] == [ROADMAP, WEEKLY]
    assert all(plan.status == ACTIVE for plan in adapted.plans)


def test_a_completed_topic_is_not_planned_again():
    """The whole point: finishing work has to buy the learner something."""
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    done = weekly(generated).items[0]
    complete(planning, done.id)

    adapted = planning.planner().adapt(planning.goal.id)

    planned = {item.topic.id for item in roadmap(adapted).items}
    assert done.topic.id not in planned
    assert adapted.completed_topic_count == 1
    assert adapted.remaining_topic_count == 2


def test_a_topic_completed_on_a_plan_since_superseded_stays_completed():
    """Superseding a plan does not un-complete the work done under it."""
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    done = weekly(generated).items[0]
    complete(planning, done.id)
    planning.planner().adapt(planning.goal.id)

    again = planning.planner().adapt(planning.goal.id)

    assert done.topic.id not in {item.topic.id for item in roadmap(again).items}
    assert again.completed_topic_count == 1


def test_an_overdue_item_is_marked_postponed_on_the_plan_being_replaced():
    """The answer ADR-021 could not give to where postponed work moves to."""
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    overdue = weekly(generated).items[0]
    planning.clock.instant = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)

    adapted = planning.planner().adapt(planning.goal.id)

    assert overdue.id in adapted.postponed_plan_item_ids
    stored = planning.plans.find_plan_item(overdue.id)
    assert stored.status == POSTPONED
    assert stored.completed_at is None


def test_a_postponed_topic_is_planned_again():
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    overdue = weekly(generated).items[0]
    planning.clock.instant = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)

    adapted = planning.planner().adapt(planning.goal.id)

    assert overdue.topic.id in {item.topic.id for item in roadmap(adapted).items}


def test_a_completed_item_is_never_postponed_however_late_it_was_done():
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    done = weekly(generated).items[0]
    complete(planning, done.id)
    planning.clock.instant = datetime(2026, 8, 20, 9, 0, tzinfo=UTC)

    adapted = planning.planner().adapt(planning.goal.id)

    assert done.id not in adapted.postponed_plan_item_ids
    assert planning.plans.find_plan_item(done.id).status == COMPLETED


def test_an_undated_roadmap_item_is_never_postponed():
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    planning.clock.instant = datetime(2027, 1, 1, 9, 0, tzinfo=UTC)

    adapted = planning.planner().adapt(planning.goal.id)

    roadmap_items = {item.id for item in roadmap(generated).items}
    assert not roadmap_items & set(adapted.postponed_plan_item_ids)


def test_adapting_keeps_the_superseded_plan_readable():
    """Superseding rather than deleting is what makes plan history worth having."""
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    week = weekly(generated)
    planner = planning.planner()
    planner.adapt(planning.goal.id)

    stored = planner.read(week.id)

    assert stored.status == SUPERSEDED
    assert stored.generation_reason == week.generation_reason
    assert stored.item_count == week.item_count


def test_the_adapted_roadmap_explains_what_changed():
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    complete(planning, weekly(generated).items[0].id)

    adapted = planning.planner().adapt(planning.goal.id)

    reason = roadmap(adapted).generation_reason
    assert "2 topics still to work through" in reason
    assert "1 topics you have already completed are not planned again" in reason


def test_adapting_when_everything_is_completed_says_so_rather_than_failing():
    planning = Planning(availability={"thursday": 480})
    generated = planning.generate()
    for item in weekly(generated).items:
        complete(planning, item.id)

    adapted = planning.planner().adapt(planning.goal.id)

    assert adapted.remaining_topic_count == 0
    assert roadmap(adapted).item_count == 0
    assert "no work left in it" in roadmap(adapted).generation_reason
    assert [plan.plan_type for plan in adapted.plans] == [ROADMAP]


def test_adapting_writes_no_learning_stage():
    """A plan item records whether planned work happened, not that a topic is
    understood -- rule 4 of the domain model, which adaptation must not breach."""
    planning = Planning(availability={"thursday": 120})
    generated = planning.generate()
    complete(planning, weekly(generated).items[0].id)

    planning.planner().adapt(planning.goal.id)

    assert planning.progress.records == []


def test_adapting_uses_the_same_ordering_rule_as_generation():
    """An adapted plan is a real plan, not a generated one with holes in it."""
    planning = Planning(availability={"thursday": 120})
    planning.generate()

    adapted = planning.planner().adapt(planning.goal.id)

    assert [item.topic.id for item in roadmap(adapted).items] == [
        planning.logic.id,
        planning.sets.id,
        planning.scheduling.id,
    ]


def test_adapting_reports_no_total_for_a_day_or_a_week():
    planning = Planning(availability={"thursday": 120})
    planning.generate()

    adapted = planning.planner().adapt(planning.goal.id)

    for plan in adapted.plans:
        assert "total" not in (plan.generation_reason or "").lower()


def test_adapting_a_goal_with_no_active_plan_is_refused():
    """Building a first plan from nothing is PLN-001's work, not this one's."""
    planning = Planning(availability={"thursday": 120})

    with pytest.raises(NoActivePlanToAdaptError):
        planning.planner().adapt(planning.goal.id)


def test_adapting_a_goal_that_is_not_stored_is_refused():
    with pytest.raises(StudyGoalNotFoundError):
        Planning().planner().adapt(uuid.uuid4())


def test_adapting_another_learners_goal_reports_it_as_missing():
    planning = Planning(availability={"thursday": 120})
    planning.generate()
    planning.learners.learners = [learner(display_name="Someone else")]

    with pytest.raises(StudyGoalNotFoundError):
        planning.planner().adapt(planning.goal.id)


def test_adapting_with_no_learner_stored_is_refused():
    planning = Planning(availability={"thursday": 120})
    planning.generate()
    planning.learners.learners = []

    with pytest.raises(LearnerNotSetUpError):
        planning.planner().adapt(planning.goal.id)


def test_adapting_with_more_than_one_learner_stored_is_refused():
    planning = Planning(availability={"thursday": 120})
    planning.generate()
    planning.learners.add_learner(learner(display_name="Second"))

    with pytest.raises(AmbiguousLocalLearnerError):
        planning.planner().adapt(planning.goal.id)


def test_adapting_is_deterministic():
    """The same inputs produce the same adapted plan, as generation does."""

    def build():
        planning = Planning(availability={"thursday": 120})
        generated = planning.generate()
        complete(planning, weekly(generated).items[0].id)
        return planning.planner().adapt(planning.goal.id)

    first, second = build(), build()

    assert first.remaining_topic_count == second.remaining_topic_count
    assert [plan.generation_reason for plan in first.plans] == [
        plan.generation_reason for plan in second.plans
    ]
