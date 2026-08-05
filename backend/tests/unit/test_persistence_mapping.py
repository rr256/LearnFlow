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
from app.infrastructure.persistence.learner_planning import STUDY_GOAL_STATUSES, Learner, StudyGoal
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
    """Guards the agreed scope. `availability_slots` and `study_plans` complete the
    learner-planning area in later milestones, and `revision_records` and
    `study_activities` complete the progress area; each waits for the code that
    reads it, so no column fixes a convention before a requirement constrains it."""
    for table_name in (
        "availability_slots",
        "study_plans",
        "plan_items",
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
