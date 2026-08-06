"""Tests for the persistence mapping.

These compile DDL for the PostgreSQL dialect rather than executing it, so they
need no database and stay in the unit suite. They guard the properties the
hand-written migrations were built against: table and constraint names, the
constraints whose behaviour depends on a PostgreSQL-specific clause, and the
column types docs/database/schema.md specifies.

Whether the migrations and these models actually agree is settled against a live
database by tests/integration/test_curriculum_migration.py and
tests/integration/test_examination_schedule_migration.py.
"""

import uuid

import pytest
from sqlalchemy import Boolean, Date, DateTime, Integer, String, Uuid
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.curriculum import (
    CURRICULUM_VERSION_STATUSES,
    TOPIC_RELATIONSHIP_TYPES,
    CurriculumVersion,
    LearningProgram,
    Topic,
    TopicRelationship,
)
from app.infrastructure.persistence.examination_schedule import (
    EXAMINATION_PERIOD_TYPES,
    EXAMINATION_SCHEDULE_STATUSES,
    ExaminationPeriod,
    ExaminationSchedule,
)
from app.infrastructure.persistence.learner_planning import (
    MAXIMUM_SESSION_MINUTES,
    MINIMUM_SESSION_MINUTES,
    MINUTES_IN_A_DAY,
    PLAN_ITEM_ACTIONS,
    PLAN_ITEM_STATUSES,
    PLAN_STATUSES,
    PLAN_TYPES,
    STUDY_GOAL_STATUSES,
    TOPIC_SEQUENCING_CHOICES,
    WEEKDAYS,
    AvailabilitySlot,
    Learner,
    PlanItem,
    StudyGoal,
    StudyPlan,
)
from app.infrastructure.persistence.progress import (
    LEARNING_STAGES,
    STAGE_SOURCES,
    LearnerTopicProgress,
)

CURRICULUM_TABLES = (
    "learning_programs",
    "curriculum_versions",
    "subjects",
    "topics",
    "topic_relationships",
)

EXAMINATION_TABLES = (
    "examination_schedules",
    "examination_periods",
)

LEARNER_PLANNING_TABLES = (
    "learners",
    "study_goals",
    "availability_slots",
    "study_plans",
    "plan_items",
)

PROGRESS_TABLES = ("learner_topic_progress",)

MAPPED_TABLES = CURRICULUM_TABLES + EXAMINATION_TABLES + LEARNER_PLANNING_TABLES + PROGRESS_TABLES


def compiled(table_name: str) -> str:
    """Render CREATE TABLE for the PostgreSQL dialect."""
    return str(CreateTable(Base.metadata.tables[table_name]).compile(dialect=postgresql.dialect()))


def constraint_names(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {constraint.name for constraint in table.constraints if constraint.name}


def test_only_the_migrated_tables_are_mapped():
    """Resource, assessment, and the remaining planning tables arrive with their milestones."""
    assert set(Base.metadata.tables) == set(MAPPED_TABLES)


@pytest.mark.parametrize("table_name", MAPPED_TABLES)
def test_every_table_has_a_conventionally_named_primary_key(table_name):
    assert f"pk_{table_name}" in constraint_names(table_name)


def test_topic_uniqueness_covers_root_topics():
    """Without NULLS NOT DISTINCT a subject could hold two identically named
    root topics, because every root topic's parent is NULL and PostgreSQL
    treats each NULL as distinct."""
    ddl = compiled("topics")

    assert (
        "CONSTRAINT uq_topics_subject_id_parent_topic_id_name "
        "UNIQUE NULLS NOT DISTINCT (subject_id, parent_topic_id, name)" in ddl
    )


def test_topic_code_is_unique_within_its_subject():
    ddl = compiled("topics")

    assert "CONSTRAINT uq_topics_subject_id_code UNIQUE (subject_id, code)" in ddl


def test_topic_code_uniqueness_keeps_nulls_distinct():
    """The opposite of the name constraint, deliberately. `code` is optional and
    the curated GATE CSE curriculum leaves it NULL throughout; under NULLS NOT
    DISTINCT a subject could hold only one uncoded topic."""
    ddl = compiled("topics")

    code_constraint = next(line for line in ddl.splitlines() if "uq_topics_subject_id_code" in line)

    assert "NULLS NOT DISTINCT" not in code_constraint


def test_only_one_curriculum_version_per_program_can_be_active():
    index = next(
        index
        for index in CurriculumVersion.__table__.indexes
        if index.name == "uq_curriculum_versions_active_learning_program_id"
    )

    ddl = str(CreateIndex(index).compile(dialect=postgresql.dialect()))

    assert "CREATE UNIQUE INDEX" in ddl
    assert "WHERE status = 'active'" in ddl


def test_curriculum_version_status_is_constrained_to_the_documented_values():
    ddl = compiled("curriculum_versions")

    assert "ck_curriculum_versions_status_is_known" in ddl
    for status in CURRICULUM_VERSION_STATUSES:
        assert f"'{status}'" in ddl


def test_topic_relationship_type_is_constrained_to_the_documented_values():
    ddl = compiled("topic_relationships")

    assert "ck_topic_relationships_relationship_type_is_known" in ddl
    for relationship_type in TOPIC_RELATIONSHIP_TYPES:
        assert f"'{relationship_type}'" in ddl


def test_a_topic_cannot_relate_to_itself():
    ddl = compiled("topic_relationships")

    assert "ck_topic_relationships_source_and_target_differ" in ddl
    assert "source_topic_id <> target_topic_id" in ddl


def test_topic_relationship_is_keyed_on_source_target_and_type():
    key = TopicRelationship.__table__.primary_key

    assert [column.name for column in key.columns] == [
        "source_topic_id",
        "target_topic_id",
        "relationship_type",
    ]


def test_every_timestamp_column_is_timezone_aware():
    """schema.md requires timestamptz throughout, not a naive local timestamp.

    Every DateTime column is checked, not just the audit ones. A bare
    ``Mapped[datetime]`` annotation maps to a naive DateTime, so a column that
    omits an explicit type silently violates the convention while still looking
    correct in the migration.
    """
    naive: list[str] = []
    for table_name in MAPPED_TABLES:
        for column in Base.metadata.tables[table_name].columns:
            if isinstance(column.type, DateTime) and not column.type.timezone:
                naive.append(f"{table_name}.{column.name}")

    assert naive == []


@pytest.mark.parametrize("table_name", MAPPED_TABLES)
def test_creation_timestamps_are_recorded(table_name):
    created_at = Base.metadata.tables[table_name].columns["created_at"]

    assert isinstance(created_at.type, DateTime)
    assert created_at.nullable is False
    assert created_at.server_default is not None


def test_topic_relationships_records_creation_only():
    """It is write-once reference data: a changed type is a different edge."""
    assert "updated_at" not in TopicRelationship.__table__.columns
    assert "updated_at" in LearningProgram.__table__.columns


def test_identifiers_are_uuids_generated_by_the_application():
    identifier = LearningProgram.__table__.columns["id"]

    assert isinstance(identifier.type, Uuid)
    assert identifier.default is not None
    assert isinstance(identifier.default.arg(None), uuid.UUID)


def test_topic_ordering_and_trackability_use_the_documented_types():
    columns = Topic.__table__.columns

    assert isinstance(columns["position"].type, Integer)
    assert columns["position"].nullable is False
    assert isinstance(columns["is_trackable"].type, Boolean)
    assert columns["is_trackable"].nullable is False


def test_the_remaining_schema_areas_are_absent():
    """Guards the agreed scope. `study_plans` and `plan_items` have arrived with
    the planning code that reads them, completing the learner-planning area;
    `revision_records` and `study_activities` complete the progress area, and the
    resource and assessment areas follow with their own milestones. Each waits for
    the code that reads it, so no column fixes a shape before a requirement
    constrains it."""
    for table_name in (
        "study_activities",
        "revision_records",
        "resources",
        "checkpoint_quizzes",
    ):
        assert table_name not in Base.metadata.tables


# -- examination schedule ---------------------------------------------------


def test_a_cycle_is_unique_within_its_learning_program():
    ddl = compiled("examination_schedules")

    assert (
        "CONSTRAINT uq_examination_schedules_learning_program_id_cycle_label "
        "UNIQUE (learning_program_id, cycle_label)" in ddl
    )


def test_examination_schedule_status_is_constrained_to_the_documented_values():
    ddl = compiled("examination_schedules")

    assert "ck_examination_schedules_schedule_status_is_known" in ddl
    for status in EXAMINATION_SCHEDULE_STATUSES:
        assert f"'{status}'" in ddl


def test_a_schedule_must_name_the_source_it_came_from():
    """A stored date with no traceable origin cannot be checked when it changes."""
    columns = ExaminationSchedule.__table__.columns

    assert columns["source_reference"].nullable is False
    assert columns["source_checked_on"].nullable is False
    assert isinstance(columns["source_checked_on"].type, Date)


def test_examination_period_type_is_constrained_to_the_documented_values():
    ddl = compiled("examination_periods")

    assert "ck_examination_periods_period_type_is_known" in ddl
    for period_type in EXAMINATION_PERIOD_TYPES:
        assert f"'{period_type}'" in ddl


def test_a_period_cannot_end_before_it_starts():
    ddl = compiled("examination_periods")

    assert "ck_examination_periods_ends_on_is_not_before_starts_on" in ddl
    # `>=`, not `>`: a single-day event stores the same date twice.
    assert "ends_on >= starts_on" in ddl


def test_a_period_is_keyed_on_its_schedule_type_and_start_date():
    """A cycle holds several periods of one type -- GATE 2027 is sat over three
    weekends -- so the type alone cannot identify one."""
    ddl = compiled("examination_periods")

    assert (
        "CONSTRAINT uq_examination_periods_schedule_id_period_type_starts_on "
        "UNIQUE (examination_schedule_id, period_type, starts_on)" in ddl
    )


def test_every_constraint_name_fits_a_postgresql_identifier():
    """PostgreSQL truncates past 63 characters, and a truncated name is one a
    downgrade cannot drop. Two names on `examination_periods` are shortened by
    hand for exactly this reason; this catches the next one."""
    too_long = {
        constraint.name
        for table_name in MAPPED_TABLES
        for constraint in Base.metadata.tables[table_name].constraints
        if constraint.name and len(constraint.name) > 63
    } | {
        index.name
        for table_name in MAPPED_TABLES
        for index in Base.metadata.tables[table_name].indexes
        if index.name and len(index.name) > 63
    }

    assert too_long == set()


def test_examination_dates_are_date_only():
    """A published calendar date carries no time and no zone to interpret one in."""
    columns = ExaminationPeriod.__table__.columns

    assert isinstance(columns["starts_on"].type, Date)
    assert isinstance(columns["ends_on"].type, Date)


# -- learner planning -------------------------------------------------------


def test_a_learner_carries_a_bounded_timezone():
    columns = Learner.__table__.columns

    assert isinstance(columns["timezone"].type, String)
    assert columns["timezone"].nullable is False
    assert columns["timezone"].server_default is None


def test_study_goal_status_is_constrained_to_the_documented_values():
    ddl = compiled("study_goals")

    assert "ck_study_goals_status_is_known" in ddl
    for status in STUDY_GOAL_STATUSES:
        assert f"'{status}'" in ddl


def test_a_study_goal_must_aim_at_a_date_or_an_examination():
    """Both columns are nullable so neither has to be invented, but a goal with
    neither has no horizon to plan against."""
    ddl = compiled("study_goals")
    columns = StudyGoal.__table__.columns

    assert columns["target_date"].nullable is True
    assert columns["examination_schedule_id"].nullable is True
    assert "ck_study_goals_aims_at_a_date_or_an_examination" in ddl
    assert "target_date IS NOT NULL OR examination_schedule_id IS NOT NULL" in ddl


def test_a_study_goal_references_a_schedule_rather_than_copying_its_dates():
    """A revised schedule then reaches every goal pointing at it."""
    columns = StudyGoal.__table__.columns

    assert {key.column.table.name for key in columns["examination_schedule_id"].foreign_keys} == {
        "examination_schedules"
    }
    assert "examination_starts_on" not in columns
    assert "examination_ends_on" not in columns


def test_learner_owned_records_carry_a_learner_id():
    """Kept from the start so multiple accounts stay an authentication change."""
    assert "learner_id" in StudyGoal.__table__.columns
    assert "user_id" not in StudyGoal.__table__.columns


# -- planning preferences ---------------------------------------------------


def test_planning_preferences_are_typed_columns_rather_than_a_json_payload():
    """ADR-019. docs/database/schema.md first described a single
    `planning_preferences jsonb`, but that same document reserves `jsonb` for
    flexible provider and resource payloads, and no CHECK can guard a key inside
    one -- so a controlled value stored that way would carry exactly the silent
    mis-mapping risk ADR-018 removed from `day_of_week`."""
    columns = StudyGoal.__table__.columns

    assert "planning_preferences" not in columns
    assert isinstance(columns["preferred_session_minutes"].type, Integer)
    assert isinstance(columns["topic_sequencing"].type, String)


def test_an_unset_preference_is_null_rather_than_a_stored_default():
    """What keeps a preference nobody set distinguishable from one the product
    guessed -- the distinction ADR-017 drew between an explicit `not_explored` and
    no record, and ADR-018 drew between zero minutes and no row."""
    columns = StudyGoal.__table__.columns

    for name in ("preferred_session_minutes", "topic_sequencing"):
        assert columns[name].nullable is True
        assert columns[name].server_default is None
        assert columns[name].default is None


def test_topic_sequencing_is_constrained_to_the_documented_values():
    ddl = compiled("study_goals")

    assert "ck_study_goals_topic_sequencing_is_known" in ddl
    for choice in TOPIC_SEQUENCING_CHOICES:
        assert f"'{choice}'" in ddl


def test_the_stored_topic_orders_are_both_derivable_from_stored_data():
    """`syllabus_order` follows the `position` columns the curriculum already has,
    and `prerequisites_first` the `prerequisite` edges in `topic_relationships`.
    No priority-focus order is offered, because the evidence that would rank
    topics that way is not stored."""
    assert TOPIC_SEQUENCING_CHOICES == ("syllabus_order", "prerequisites_first")


def test_a_preferred_session_length_stays_inside_the_bounds_a_plan_can_honour():
    ddl = compiled("study_goals")

    assert "ck_study_goals_preferred_session_minutes_within_bounds" in ddl
    # `IS NULL OR` is written out rather than left to three-valued CHECK
    # semantics, so a reader need not recall that a CHECK passes on NULL.
    assert "preferred_session_minutes IS NULL OR" in ddl
    assert f"preferred_session_minutes >= {MINIMUM_SESSION_MINUTES}" in ddl
    assert f"preferred_session_minutes <= {MAXIMUM_SESSION_MINUTES}" in ddl


def test_a_preference_stores_no_clock_time():
    """A preferred session length is a duration, the same kind of value as
    `available_minutes`. ADR-018's refusal to store a time of day stands."""
    columns = StudyGoal.__table__.columns

    assert "preferred_session_starts_at" not in columns
    assert "study_starts_at" not in columns


# -- availability -----------------------------------------------------------


def test_the_day_of_week_is_stored_as_a_name_not_a_number():
    """ADR-018. docs/database/schema.md first described a `smallint` holding 0-6
    "according to documented convention", which left a numbering for a reader or
    a client to get wrong -- and Python, JavaScript, and PostgreSQL disagree about
    which day is zero. A stored name has no convention to mis-map, and it matches
    every other controlled value in the schema."""
    columns = AvailabilitySlot.__table__.columns

    assert isinstance(columns["day_of_week"].type, String)
    assert columns["day_of_week"].nullable is False
    assert not isinstance(columns["day_of_week"].type, Integer)


def test_the_day_of_week_is_constrained_to_the_seven_documented_days():
    ddl = compiled("availability_slots")

    assert "ck_availability_slots_day_of_week_is_known" in ddl
    for day in WEEKDAYS:
        assert f"'{day}'" in ddl


def test_the_stored_days_are_the_seven_of_a_week_in_week_order():
    """The order is presentation, not a stored rank: no column carries it, and
    nothing compares two days."""
    assert WEEKDAYS == (
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    )


def test_a_goal_holds_one_availability_slot_per_day():
    """What makes saving a week rewrite the days it names rather than appending a
    second Monday beside the first."""
    ddl = compiled("availability_slots")

    assert (
        "CONSTRAINT uq_availability_slots_study_goal_id_day_of_week "
        "UNIQUE (study_goal_id, day_of_week)" in ddl
    )


def test_available_minutes_cannot_exceed_the_minutes_in_a_day():
    """schema.md approves the lower bound. The upper bound is added because a day
    holds 1440 minutes, so anything larger is a mistake rather than ambition."""
    ddl = compiled("availability_slots")
    columns = AvailabilitySlot.__table__.columns

    assert "ck_availability_slots_available_minutes_within_a_day" in ddl
    assert f"available_minutes >= 0 AND available_minutes <= {MINUTES_IN_A_DAY}" in ddl
    assert isinstance(columns["available_minutes"].type, Integer)
    assert columns["available_minutes"].nullable is False


def test_availability_belongs_to_a_study_goal_rather_than_to_a_learner():
    """A learner who archives one goal and starts another is describing a
    different week, so the row hangs off the goal -- as schema.md has it."""
    columns = AvailabilitySlot.__table__.columns

    assert {key.column.table.name for key in columns["study_goal_id"].foreign_keys} == {
        "study_goals"
    }
    assert "learner_id" not in columns


def test_availability_stores_no_clock_time():
    """A slot is a day's worth of minutes, not a sitting between two times.
    Storing wall-clock times would raise which zone reads them, which nothing
    this feature does needs."""
    columns = AvailabilitySlot.__table__.columns

    assert "starts_at" not in columns
    assert "ends_at" not in columns


# -- progress ---------------------------------------------------------------


def test_learning_stage_is_constrained_to_the_five_approved_stages():
    ddl = compiled("learner_topic_progress")

    assert "ck_learner_topic_progress_learning_stage_is_known" in ddl
    for stage in LEARNING_STAGES:
        assert f"'{stage}'" in ddl


def test_the_stored_learning_stages_are_the_five_terminology_defines():
    """The stored form is `snake_case`; docs/domain/terminology.md holds the
    display labels a learner sees. Renaming a label must not become a migration,
    so the two are deliberately different representations of the same five."""
    assert LEARNING_STAGES == (
        "not_explored",
        "building_foundation",
        "developing_confidence",
        "practice_ready",
        "strong_understanding",
    )


def test_stage_source_is_constrained_to_the_documented_values():
    ddl = compiled("learner_topic_progress")

    assert "ck_learner_topic_progress_stage_source_is_known" in ddl
    for source in STAGE_SOURCES:
        assert f"'{source}'" in ddl


def test_a_learner_holds_one_progress_record_per_topic():
    """What makes recording a stage an update of the existing row rather than a
    second row beside it. schema.md lists it under Required Indexes."""
    ddl = compiled("learner_topic_progress")

    assert (
        "CONSTRAINT uq_learner_topic_progress_learner_id_topic_id "
        "UNIQUE (learner_id, topic_id)" in ddl
    )


def test_topic_progress_carries_a_learner_id():
    assert "learner_id" in LearnerTopicProgress.__table__.columns
    assert "user_id" not in LearnerTopicProgress.__table__.columns


def test_the_progress_columns_awaiting_their_own_code_are_absent():
    """schema.md holds three further columns as an approved target. Each arrives
    with the change that writes it, per ADR-011 and ADR-017: `material_status`
    and `material_completed_at` with material completion, and `last_studied_at`
    with `study_activities`, which does not exist."""
    columns = LearnerTopicProgress.__table__.columns

    assert "material_status" not in columns
    assert "material_completed_at" not in columns
    assert "last_studied_at" not in columns


def test_a_stage_always_has_a_value_and_a_source():
    """Neither is nullable and neither has a database default. A row that cannot
    say where its stage came from is one a later derived writer could overwrite
    without knowing it was discarding a learner's own answer."""
    columns = LearnerTopicProgress.__table__.columns

    assert columns["learning_stage"].nullable is False
    assert columns["learning_stage"].server_default is None
    assert columns["stage_source"].nullable is False
    assert columns["stage_source"].server_default is None


# -- study plans ------------------------------------------------------------


def test_plan_type_is_constrained_to_the_documented_values():
    """docs/database/schema.md describes `plan_type` as bare `text`. It is
    validated text guarded by a CHECK here, following that document's own
    Conventions and ADR-011's rule, as `day_of_week` and `topic_sequencing`
    already do. ADR-020 records the departure."""
    ddl = compiled("study_plans")

    assert "ck_study_plans_plan_type_is_known" in ddl
    for plan_type in PLAN_TYPES:
        assert f"'{plan_type}'" in ddl


def test_plan_status_is_constrained_to_the_documented_values():
    ddl = compiled("study_plans")

    assert "ck_study_plans_status_is_known" in ddl
    for status in PLAN_STATUSES:
        assert f"'{status}'" in ddl


def test_a_plan_type_is_stored_as_text_rather_than_a_number():
    columns = StudyPlan.__table__.columns

    assert isinstance(columns["plan_type"].type, String)
    assert columns["plan_type"].nullable is False


def test_a_plan_can_be_superseded_rather_than_deleted():
    """docs/database/schema.md asks that plans be superseded so a learner's plan
    history stays explainable; the status is what carries that."""
    assert "superseded" in PLAN_STATUSES


def test_a_plan_carries_both_the_learner_and_the_goal():
    """schema.md carries both, and the required index leads on `learner_id`, so
    a learner's plans are reachable without joining through their goals."""
    columns = StudyPlan.__table__.columns

    assert columns["learner_id"].nullable is False
    assert columns["study_goal_id"].nullable is False
    assert "user_id" not in columns


def test_a_plan_period_may_be_open_at_either_end():
    """A roadmap has no end date when the goal aims at an examination schedule
    publishing no sitting day and carries no target date beside it."""
    columns = StudyPlan.__table__.columns

    assert columns["period_start"].nullable is True
    assert columns["period_end"].nullable is True
    assert isinstance(columns["period_start"].type, Date)


def test_the_plan_index_is_the_one_schema_md_requires():
    names = {index.name for index in StudyPlan.__table__.indexes}

    assert "ix_study_plans_learner_id_study_goal_id_status_period_start" in names


# -- plan items -------------------------------------------------------------


def test_plan_item_action_is_constrained_to_the_documented_values():
    ddl = compiled("plan_items")

    assert "ck_plan_items_action_type_is_known" in ddl
    for action in PLAN_ITEM_ACTIONS:
        assert f"'{action}'" in ddl


def test_plan_item_status_is_constrained_to_the_documented_values():
    ddl = compiled("plan_items")

    assert "ck_plan_items_status_is_known" in ddl
    for status in PLAN_ITEM_STATUSES:
        assert f"'{status}'" in ddl


def test_an_item_cannot_be_estimated_at_zero_minutes():
    """schema.md approves the bound. An item of zero minutes is scheduling
    overhead rather than study."""
    ddl = compiled("plan_items")

    assert "ck_plan_items_estimated_minutes_is_positive" in ddl
    assert "estimated_minutes IS NULL OR estimated_minutes > 0" in ddl


def test_an_item_may_recommend_work_belonging_to_no_topic():
    """schema.md has `topic_id` nullable. Nothing writes one today; every item the
    planner produces names a topic."""
    assert PlanItem.__table__.columns["topic_id"].nullable is True


def test_an_item_always_has_a_priority_and_a_status():
    columns = PlanItem.__table__.columns

    assert columns["priority"].nullable is False
    assert columns["status"].nullable is False
    assert columns["status"].server_default is None


def test_a_roadmap_item_can_carry_no_date():
    """A roadmap says what order to work in, not which day to do it on."""
    assert PlanItem.__table__.columns["scheduled_for"].nullable is True


def test_the_plan_item_index_is_the_one_schema_md_requires():
    names = {index.name for index in PlanItem.__table__.indexes}

    assert "ix_plan_items_study_plan_id_scheduled_for_status" in names
