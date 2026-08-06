"""Unit tests for the study-goal use case (GOAL-001 to GOAL-005).

They run against fakes, so they exercise the rules ADR-013 fixed -- a goal aims
at something, the examination is a window, a goal binds to the active curriculum
version -- the ones ADR-018 fixed for a week of availability, and the ones ADR-019
fixed for a group of planning preferences, without a database.
"""

import uuid
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.application.dto.availability import (
    AvailabilitySlotEntry,
    WeeklyAvailabilityRequest,
)
from app.application.dto.planning_preferences import PlanningPreferences
from app.application.dto.study_goal import NewStudyGoal, StudyGoalChanges
from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
)
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_study_goals import (
    ActiveGoalExistsError,
    AvailableMinutesOutOfRangeError,
    DuplicateWeekdayError,
    EmptyGoalUpdateError,
    LearnerNotSetUpError,
    ManageStudyGoals,
    MissingGoalTargetError,
    SessionMinutesOutOfRangeError,
    StudyGoalNotFoundError,
    UnknownGoalStatusError,
    UnknownReferenceError,
    UnknownTopicSequencingError,
    UnknownWeekdayError,
)
from tests.unit.fake_examination_schedule_repository import FakeExaminationScheduleRepository
from tests.unit.fake_learner_repository import FakeLearnerRepository, learner
from tests.unit.fake_study_goal_management_repository import (
    FakeStudyGoalManagementRepository,
)
from tests.unit.schedule_fixtures import PROGRAM_ID, build_schedule, gate_2027_periods

PROGRAM = LearningProgramRecord(
    id=PROGRAM_ID,
    code="gate-cse",
    name="GATE Computer Science and Information Technology",
    description=None,
)
ACTIVE_VERSION = CurriculumVersionRecord(
    id=uuid.uuid4(),
    learning_program_id=PROGRAM_ID,
    version_label="2027",
    status="active",
    source_reference=None,
    published_at=datetime(2026, 7, 31, tzinfo=UTC),
)
RETIRED_VERSION = CurriculumVersionRecord(
    id=uuid.uuid4(),
    learning_program_id=PROGRAM_ID,
    version_label="2026",
    status="retired",
    source_reference=None,
    published_at=datetime(2025, 7, 31, tzinfo=UTC),
)


class Workspace:
    """A wired use case with its fakes reachable for assertions."""

    def __init__(self, *, learners=(), goals=(), schedules=(), periods=(), versions=None):
        self.learners = FakeLearnerRepository(tuple(learners))
        self.goals = FakeStudyGoalManagementRepository(
            programs=[PROGRAM],
            versions=[ACTIVE_VERSION, RETIRED_VERSION] if versions is None else versions,
            goals=goals,
        )
        self.schedules = FakeExaminationScheduleRepository(schedules=schedules, periods=periods)
        self.use_case = ManageStudyGoals(
            learners=self.learners, goals=self.goals, schedules=self.schedules
        )


@pytest.fixture
def schedule():
    return build_schedule()


@pytest.fixture
def workspace(schedule):
    stored = learner()
    return Workspace(
        learners=[stored], schedules=[schedule], periods=gate_2027_periods(schedule.id)
    )


# -- GOAL-001: create ------------------------------------------------------


def test_creating_a_goal_binds_it_to_the_programs_active_curriculum_version(workspace, schedule):
    """A client chooses a program, not a syllabus revision."""
    goal = workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
    )

    assert goal.curriculum_version.id == ACTIVE_VERSION.id
    assert goal.curriculum_version.status == "active"


def test_a_created_goal_reports_the_examination_as_a_window(workspace, schedule):
    goal = workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
    )

    assert goal.examination is not None
    assert goal.examination.window_starts_on == date(2027, 2, 6)
    assert goal.examination.window_ends_on == date(2027, 2, 21)


def test_a_created_goal_carries_the_schedules_provenance_and_status(workspace, schedule):
    """A provisional date shown without that word reads as settled fact."""
    goal = workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
    )

    assert goal.examination is not None
    assert goal.examination.schedule_status == "provisional"
    assert goal.examination.source_reference == schedule.source_reference
    assert goal.examination.source_checked_on == schedule.source_checked_on


def test_a_goal_may_aim_at_a_target_date_alone(workspace):
    goal = workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, target_date=date(2027, 1, 31))
    )

    assert goal.target_date == date(2027, 1, 31)
    assert goal.examination is None


def test_a_goal_may_aim_at_both_a_cycle_and_a_date(workspace, schedule):
    goal = workspace.use_case.create(
        NewStudyGoal(
            learning_program_id=PROGRAM_ID,
            examination_schedule_id=schedule.id,
            target_date=date(2027, 1, 31),
        )
    )

    assert goal.target_date == date(2027, 1, 31)
    assert goal.examination is not None


def test_creating_refuses_a_goal_that_aims_at_nothing(workspace):
    """The database enforces the same rule; failing it there would be a 500."""
    with pytest.raises(MissingGoalTargetError):
        workspace.use_case.create(NewStudyGoal(learning_program_id=PROGRAM_ID))


def test_creating_refuses_before_a_learner_exists(schedule):
    workspace = Workspace(schedules=[schedule])

    with pytest.raises(LearnerNotSetUpError):
        workspace.use_case.create(
            NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
        )


def test_creating_refuses_an_unknown_learning_program(workspace):
    with pytest.raises(UnknownReferenceError) as raised:
        workspace.use_case.create(
            NewStudyGoal(learning_program_id=uuid.uuid4(), target_date=date(2027, 1, 31))
        )

    assert raised.value.field == "learning_program_id"


def test_creating_refuses_an_unknown_examination_schedule(workspace):
    with pytest.raises(UnknownReferenceError) as raised:
        workspace.use_case.create(
            NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=uuid.uuid4())
        )

    assert raised.value.field == "examination_schedule_id"


def test_creating_refuses_a_schedule_belonging_to_another_learning_program():
    """No constraint forbids it: the goal references program and schedule separately."""
    other = build_schedule(learning_program_id=uuid.uuid4())
    workspace = Workspace(learners=[learner()], schedules=[other])

    with pytest.raises(UnknownReferenceError) as raised:
        workspace.use_case.create(
            NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=other.id)
        )

    assert raised.value.field == "examination_schedule_id"


def test_creating_refuses_a_program_with_no_active_curriculum_version(schedule):
    workspace = Workspace(learners=[learner()], schedules=[schedule], versions=[RETIRED_VERSION])

    with pytest.raises(UnknownReferenceError):
        workspace.use_case.create(
            NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
        )


def test_creating_a_second_active_goal_for_the_same_program_is_refused(workspace, schedule):
    """The existing goal is what a plan was built from; a repeat submit must not replace it."""
    request = NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
    workspace.use_case.create(request)

    with pytest.raises(ActiveGoalExistsError):
        workspace.use_case.create(request)


def test_a_paused_goal_does_not_block_a_new_one(workspace, schedule):
    created = workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
    )
    workspace.use_case.update(created.id, StudyGoalChanges(status="paused"))

    second = workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, target_date=date(2027, 1, 31))
    )

    assert second.status == "active"


# -- GOAL-002 and GOAL-003: read -------------------------------------------


def test_listing_returns_an_empty_page_before_a_learner_exists(schedule):
    workspace = Workspace(schedules=[schedule])

    page = workspace.use_case.list_study_goals(limit=25, offset=0)

    assert page.goals == ()
    assert page.total == 0


def test_listing_reports_the_applied_window_and_the_total(workspace, schedule):
    workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
    )

    page = workspace.use_case.list_study_goals(limit=1, offset=0)

    assert (page.limit, page.offset, page.total) == (1, 0, 1)


def test_reading_a_goal_that_belongs_to_another_learner_reports_it_missing(workspace, schedule):
    """Saying "that exists but is not yours" would confirm an unreadable record."""
    created = workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
    )
    workspace.goals.goals[0] = replace(workspace.goals.goals[0], learner_id=uuid.uuid4())

    with pytest.raises(StudyGoalNotFoundError):
        workspace.use_case.read(created.id)


def test_reading_an_unknown_goal_reports_it_missing(workspace):
    with pytest.raises(StudyGoalNotFoundError):
        workspace.use_case.read(uuid.uuid4())


def test_a_goal_keeps_the_curriculum_version_it_was_created_against(workspace, schedule):
    """Retiring a version must not silently move a learner onto the new one."""
    created = workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
    )
    workspace.goals.versions = (
        CurriculumVersionRecord(
            id=ACTIVE_VERSION.id,
            learning_program_id=PROGRAM_ID,
            version_label="2027",
            status="retired",
            source_reference=None,
            published_at=ACTIVE_VERSION.published_at,
        ),
    )

    assert workspace.use_case.read(created.id).curriculum_version.status == "retired"


# -- GOAL-004: update ------------------------------------------------------


def test_updating_the_status_leaves_the_rest_alone(workspace, schedule):
    created = workspace.use_case.create(
        NewStudyGoal(
            learning_program_id=PROGRAM_ID,
            examination_schedule_id=schedule.id,
            target_date=date(2027, 1, 31),
        )
    )

    updated = workspace.use_case.update(created.id, StudyGoalChanges(status="paused"))

    assert updated.status == "paused"
    assert updated.target_date == date(2027, 1, 31)
    assert updated.examination is not None


def test_clearing_the_target_date_removes_it(workspace, schedule):
    created = workspace.use_case.create(
        NewStudyGoal(
            learning_program_id=PROGRAM_ID,
            examination_schedule_id=schedule.id,
            target_date=date(2027, 1, 31),
        )
    )

    updated = workspace.use_case.update(created.id, StudyGoalChanges(clear_target_date=True))

    assert updated.target_date is None
    assert updated.examination is not None


def test_updating_refuses_to_leave_a_goal_aiming_at_nothing(workspace, schedule):
    created = workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
    )

    with pytest.raises(MissingGoalTargetError):
        workspace.use_case.update(created.id, StudyGoalChanges(clear_examination_schedule=True))


def test_updating_refuses_a_request_that_changes_nothing(workspace, schedule):
    created = workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
    )

    with pytest.raises(EmptyGoalUpdateError):
        workspace.use_case.update(created.id, StudyGoalChanges())


def test_updating_refuses_a_status_the_database_would_reject(workspace, schedule):
    created = workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
    )

    with pytest.raises(UnknownGoalStatusError):
        workspace.use_case.update(created.id, StudyGoalChanges(status="finished"))


def test_updating_refuses_a_schedule_from_another_learning_program(workspace):
    other = build_schedule(learning_program_id=uuid.uuid4())
    workspace.schedules.schedules = (*workspace.schedules.schedules, other)
    created = workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, target_date=date(2027, 1, 31))
    )

    with pytest.raises(UnknownReferenceError) as raised:
        workspace.use_case.update(created.id, StudyGoalChanges(examination_schedule_id=other.id))

    assert raised.value.field == "examination_schedule_id"


def test_updating_an_unknown_goal_reports_it_missing(workspace):
    with pytest.raises(StudyGoalNotFoundError):
        workspace.use_case.update(uuid.uuid4(), StudyGoalChanges(status="paused"))


def test_updating_refuses_when_more_than_one_learner_is_stored(workspace, schedule):
    created = workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
    )
    workspace.learners.add_learner(learner())

    with pytest.raises(AmbiguousLocalLearnerError):
        workspace.use_case.update(created.id, StudyGoalChanges(status="paused"))


# -- GOAL-005: replace weekly availability ---------------------------------


def week(**days: int) -> WeeklyAvailabilityRequest:
    """A replacement week, written as `week(monday=120, tuesday=60)`."""
    return WeeklyAvailabilityRequest(
        slots=tuple(
            AvailabilitySlotEntry(day_of_week=day, available_minutes=minutes)
            for day, minutes in days.items()
        )
    )


def stored_week(workspace, goal_id):
    """The days stored against a goal, as day-to-minutes, whatever their order."""
    return {
        slot.day_of_week: slot.available_minutes
        for slot in workspace.goals.list_availability_slots([goal_id])
    }


@pytest.fixture
def goal(workspace, schedule):
    return workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
    )


def test_a_new_goal_has_an_empty_week(goal):
    """No availability is a real state, reported as an empty week rather than as
    an absent one, so no caller needs a branch for a goal that predates GOAL-005."""
    assert goal.availability.is_empty
    assert goal.availability.slots == ()


def test_saving_a_week_stores_the_days_it_names(workspace, goal):
    workspace.use_case.replace_availability(goal.id, week(monday=120, thursday=90))

    assert stored_week(workspace, goal.id) == {"monday": 120, "thursday": 90}


def test_a_saved_week_is_returned_in_week_order(workspace, goal):
    """Monday first, whatever order the request named the days in, and whatever
    order the repository returns them in."""
    saved = workspace.use_case.replace_availability(
        goal.id, week(sunday=30, tuesday=60, saturday=240)
    )

    assert [slot.day_of_week for slot in saved.slots] == ["tuesday", "saturday", "sunday"]


def test_saving_a_week_removes_a_day_it_does_not_name(workspace, goal):
    """A replacement, not a merge."""
    workspace.use_case.replace_availability(goal.id, week(monday=120, tuesday=60))

    workspace.use_case.replace_availability(goal.id, week(monday=120))

    assert stored_week(workspace, goal.id) == {"monday": 120}


def test_an_empty_week_clears_every_stored_day(workspace, goal):
    workspace.use_case.replace_availability(goal.id, week(monday=120, tuesday=60))

    saved = workspace.use_case.replace_availability(goal.id, WeeklyAvailabilityRequest(slots=()))

    assert saved.is_empty
    assert stored_week(workspace, goal.id) == {}


def test_saving_a_week_rewrites_a_day_whose_minutes_changed(workspace, goal):
    workspace.use_case.replace_availability(goal.id, week(monday=120))

    workspace.use_case.replace_availability(goal.id, week(monday=150))

    assert stored_week(workspace, goal.id) == {"monday": 150}


def test_an_unchanged_day_keeps_its_row(workspace, goal):
    """A day whose minutes have not moved is left alone entirely, so saving the
    same week twice writes nothing -- the rule PRG-004 applies to an unchanged
    stage. A delete-and-reinsert would churn the identifier and `created_at`."""
    workspace.use_case.replace_availability(goal.id, week(monday=120, tuesday=60))
    before = {slot.day_of_week: slot.id for slot in workspace.goals.availability}

    workspace.use_case.replace_availability(goal.id, week(monday=120, tuesday=90))

    after = {slot.day_of_week: slot.id for slot in workspace.goals.availability}
    assert after["monday"] == before["monday"]
    assert after["tuesday"] == before["tuesday"]


def test_a_day_with_no_available_time_is_stored(workspace, goal):
    """Zero records a day the learner deliberately keeps free, which stays
    distinguishable from a day they never set."""
    workspace.use_case.replace_availability(goal.id, week(sunday=0))

    assert stored_week(workspace, goal.id) == {"sunday": 0}


def test_a_full_day_of_availability_is_accepted(workspace, goal):
    workspace.use_case.replace_availability(goal.id, week(saturday=1440))

    assert stored_week(workspace, goal.id) == {"saturday": 1440}


def test_a_saved_week_is_read_back_on_the_goal(workspace, goal):
    workspace.use_case.replace_availability(goal.id, week(friday=45))

    read = workspace.use_case.read(goal.id)

    assert read.availability.slots == (
        AvailabilitySlotEntry(day_of_week="friday", available_minutes=45),
    )


def test_a_saved_week_is_read_back_in_the_goal_page(workspace, goal):
    workspace.use_case.replace_availability(goal.id, week(friday=45))

    page = workspace.use_case.list_study_goals(limit=25, offset=0)

    assert page.goals[0].availability.slots == (
        AvailabilitySlotEntry(day_of_week="friday", available_minutes=45),
    )


def test_a_goal_without_availability_reports_an_empty_week_in_a_page(workspace, goal):
    """Every goal in a page gets a week, so a caller never has to tell "no
    availability" from "not asked about"."""
    page = workspace.use_case.list_study_goals(limit=25, offset=0)

    assert page.goals[0].availability.is_empty


def test_one_goals_week_does_not_reach_another(workspace, goal, schedule):
    """Availability belongs to the goal, so two goals hold two weeks."""
    workspace.use_case.update(goal.id, StudyGoalChanges(status="archived"))
    second = workspace.use_case.create(
        NewStudyGoal(learning_program_id=PROGRAM_ID, examination_schedule_id=schedule.id)
    )
    workspace.use_case.replace_availability(goal.id, week(monday=120))

    assert workspace.use_case.read(second.id).availability.is_empty
    assert not workspace.use_case.read(goal.id).availability.is_empty


def test_saving_refuses_a_day_that_is_not_one_of_the_seven(workspace, goal):
    with pytest.raises(UnknownWeekdayError):
        workspace.use_case.replace_availability(goal.id, week(moonday=60))


def test_saving_refuses_a_numeric_day(workspace, goal):
    """There is no numbering convention to accept. A client sending an index is
    refused rather than silently misfiling a week (ADR-018)."""
    with pytest.raises(UnknownWeekdayError):
        workspace.use_case.replace_availability(
            goal.id,
            WeeklyAvailabilityRequest(
                slots=(AvailabilitySlotEntry(day_of_week="0", available_minutes=60),)
            ),
        )


def test_saving_refuses_the_same_day_twice(workspace, goal):
    """The unique key would see one row, not two, so this can only be caught here."""
    with pytest.raises(DuplicateWeekdayError):
        workspace.use_case.replace_availability(
            goal.id,
            WeeklyAvailabilityRequest(
                slots=(
                    AvailabilitySlotEntry(day_of_week="monday", available_minutes=60),
                    AvailabilitySlotEntry(day_of_week="monday", available_minutes=90),
                )
            ),
        )


@pytest.mark.parametrize("minutes", [-1, 1441])
def test_saving_refuses_minutes_outside_a_day(workspace, goal, minutes):
    """The database enforces the same bounds; failing them there would be a 500."""
    with pytest.raises(AvailableMinutesOutOfRangeError):
        workspace.use_case.replace_availability(goal.id, week(monday=minutes))


def test_a_refused_week_writes_nothing(workspace, goal):
    """Validation happens before the first write, so a week refused for its last
    day does not leave its first days stored."""
    workspace.use_case.replace_availability(goal.id, week(monday=120))

    with pytest.raises(UnknownWeekdayError):
        workspace.use_case.replace_availability(goal.id, week(tuesday=60, moonday=60))

    assert stored_week(workspace, goal.id) == {"monday": 120}


def test_saving_a_week_against_an_unknown_goal_reports_it_missing(workspace):
    with pytest.raises(StudyGoalNotFoundError):
        workspace.use_case.replace_availability(uuid.uuid4(), week(monday=120))


def test_saving_a_week_against_another_learners_goal_reports_it_missing(workspace, goal):
    """A goal owned by somebody else is missing rather than forbidden, the rule
    GOAL-003 already follows: saying "that exists but is not yours" would confirm
    a record the caller may not read."""
    somebody_else = uuid.uuid4()
    workspace.goals.goals = [
        replace(stored, learner_id=somebody_else) for stored in workspace.goals.goals
    ]

    with pytest.raises(StudyGoalNotFoundError):
        workspace.use_case.replace_availability(goal.id, week(monday=120))


def test_saving_a_week_refuses_when_more_than_one_learner_is_stored(workspace, goal):
    workspace.learners.add_learner(learner())

    with pytest.raises(AmbiguousLocalLearnerError):
        workspace.use_case.replace_availability(goal.id, week(monday=120))


def test_saving_a_week_totals_nothing(workspace, goal):
    """Availability is a planning input. Nothing here sums a week, compares two,
    or derives a plan from one; that arrives with Milestone 3."""
    saved = workspace.use_case.replace_availability(goal.id, week(monday=120, tuesday=60))

    assert not hasattr(saved, "total_minutes")
    assert [slot.available_minutes for slot in saved.slots] == [120, 60]


# -- planning preferences (ADR-019) ----------------------------------------


def preferences(**fields):
    """A preference group, so a test states only the choices it cares about."""
    return PlanningPreferences(**fields)


def stored_preferences(workspace, goal_id):
    """What the fake actually holds, rather than what the use case returned."""
    stored = next(record for record in workspace.goals.goals if record.id == goal_id)
    return stored.planning_preferences


def test_a_new_goal_has_no_preferences(goal):
    """An empty group rather than a null, so no caller needs a branch for a goal
    stored before preferences existed."""
    assert goal.planning_preferences.is_empty
    assert goal.planning_preferences.preferred_session_minutes is None
    assert goal.planning_preferences.topic_sequencing is None


def test_creating_a_goal_stores_the_preferences_it_names(workspace, schedule):
    goal = workspace.use_case.create(
        NewStudyGoal(
            learning_program_id=PROGRAM_ID,
            examination_schedule_id=schedule.id,
            planning_preferences=preferences(
                preferred_session_minutes=90, topic_sequencing="prerequisites_first"
            ),
        )
    )

    assert stored_preferences(workspace, goal.id) == preferences(
        preferred_session_minutes=90, topic_sequencing="prerequisites_first"
    )


def test_a_preference_left_out_is_unset_rather_than_defaulted(workspace, schedule):
    """Nothing invents a preference on the learner's behalf. A planner meeting
    None chooses its own default visibly rather than reading a value nobody
    chose, which is the distinction ADR-017 and ADR-018 both drew."""
    goal = workspace.use_case.create(
        NewStudyGoal(
            learning_program_id=PROGRAM_ID,
            examination_schedule_id=schedule.id,
            planning_preferences=preferences(topic_sequencing="syllabus_order"),
        )
    )

    assert goal.planning_preferences.preferred_session_minutes is None
    assert goal.planning_preferences.topic_sequencing == "syllabus_order"


def test_creating_refuses_an_unknown_topic_sequencing(workspace, schedule):
    with pytest.raises(UnknownTopicSequencingError):
        workspace.use_case.create(
            NewStudyGoal(
                learning_program_id=PROGRAM_ID,
                examination_schedule_id=schedule.id,
                planning_preferences=preferences(topic_sequencing="alphabetical_order"),
            )
        )


@pytest.mark.parametrize("minutes", [0, 14, 481, 1441])
def test_creating_refuses_a_session_length_outside_the_bounds(workspace, schedule, minutes):
    with pytest.raises(SessionMinutesOutOfRangeError):
        workspace.use_case.create(
            NewStudyGoal(
                learning_program_id=PROGRAM_ID,
                examination_schedule_id=schedule.id,
                planning_preferences=preferences(preferred_session_minutes=minutes),
            )
        )


@pytest.mark.parametrize("minutes", [15, 60, 480])
def test_a_session_length_on_or_inside_the_bounds_is_accepted(workspace, schedule, minutes):
    goal = workspace.use_case.create(
        NewStudyGoal(
            learning_program_id=PROGRAM_ID,
            examination_schedule_id=schedule.id,
            planning_preferences=preferences(preferred_session_minutes=minutes),
        )
    )

    assert goal.planning_preferences.preferred_session_minutes == minutes


def test_updating_preferences_replaces_the_whole_group(workspace, goal):
    """A supplied group is the goal's preferences, not a patch over them: a form
    shows every preference at once, so a member it left out was cleared."""
    workspace.use_case.update(
        goal.id,
        StudyGoalChanges(
            planning_preferences=preferences(
                preferred_session_minutes=90, topic_sequencing="syllabus_order"
            )
        ),
    )

    updated = workspace.use_case.update(
        goal.id,
        StudyGoalChanges(planning_preferences=preferences(topic_sequencing="prerequisites_first")),
    )

    assert updated.planning_preferences == preferences(topic_sequencing="prerequisites_first")


def test_an_update_naming_no_preferences_leaves_them_alone(workspace, goal):
    workspace.use_case.update(
        goal.id, StudyGoalChanges(planning_preferences=preferences(preferred_session_minutes=45))
    )

    updated = workspace.use_case.update(goal.id, StudyGoalChanges(status="paused"))

    assert updated.planning_preferences.preferred_session_minutes == 45


def test_an_empty_group_clears_every_preference(workspace, goal):
    """Replacing with nothing is how a learner takes them all back, the same way
    an empty week clears availability."""
    workspace.use_case.update(
        goal.id,
        StudyGoalChanges(
            planning_preferences=preferences(
                preferred_session_minutes=45, topic_sequencing="syllabus_order"
            )
        ),
    )

    updated = workspace.use_case.update(
        goal.id, StudyGoalChanges(planning_preferences=preferences())
    )

    assert updated.planning_preferences.is_empty
    assert stored_preferences(workspace, goal.id).is_empty


def test_naming_only_preferences_is_not_an_empty_update(workspace, goal):
    """A group is a field to change like any other, so an update carrying nothing
    else must not be refused as empty."""
    updated = workspace.use_case.update(
        goal.id, StudyGoalChanges(planning_preferences=preferences(preferred_session_minutes=30))
    )

    assert updated.planning_preferences.preferred_session_minutes == 30


def test_saving_the_preferences_already_stored_writes_nothing(workspace, goal):
    """The rule GOAL-005 and PRG-004 already follow: a repeated form submission
    must not fail or churn a row on its second attempt."""
    group = StudyGoalChanges(planning_preferences=preferences(preferred_session_minutes=60))
    workspace.use_case.update(goal.id, group)
    before = next(record for record in workspace.goals.goals if record.id == goal.id)

    workspace.use_case.update(goal.id, group)

    assert next(record for record in workspace.goals.goals if record.id == goal.id) is before


def test_updating_refuses_an_unknown_topic_sequencing(workspace, goal):
    with pytest.raises(UnknownTopicSequencingError):
        workspace.use_case.update(
            goal.id,
            StudyGoalChanges(
                planning_preferences=preferences(topic_sequencing="alphabetical_order")
            ),
        )


def test_a_refused_preference_leaves_the_stored_group_alone(workspace, goal):
    """The whole group is validated before anything is written, so a rejected
    member cannot take a valid one down with it."""
    workspace.use_case.update(
        goal.id, StudyGoalChanges(planning_preferences=preferences(preferred_session_minutes=60))
    )

    with pytest.raises(SessionMinutesOutOfRangeError):
        workspace.use_case.update(
            goal.id,
            StudyGoalChanges(
                planning_preferences=preferences(
                    preferred_session_minutes=9000, topic_sequencing="syllabus_order"
                )
            ),
        )

    assert stored_preferences(workspace, goal.id) == preferences(preferred_session_minutes=60)


def test_a_refusal_names_the_choices_without_echoing_the_rejected_value(workspace, goal):
    with pytest.raises(UnknownTopicSequencingError) as raised:
        workspace.use_case.update(
            goal.id,
            StudyGoalChanges(
                planning_preferences=preferences(topic_sequencing="alphabetical_order")
            ),
        )

    assert "syllabus_order" in str(raised.value)
    assert "alphabetical_order" not in str(raised.value)


def test_nothing_ranks_or_scores_a_preference(workspace, goal):
    """Preferences are planning inputs. Nothing here compares two of them, scores
    one, or derives a plan from either; that arrives with Milestone 3."""
    updated = workspace.use_case.update(
        goal.id,
        StudyGoalChanges(
            planning_preferences=preferences(
                preferred_session_minutes=60, topic_sequencing="syllabus_order"
            )
        ),
    )

    assert not hasattr(updated.planning_preferences, "score")
    assert not hasattr(updated.planning_preferences, "weight")
