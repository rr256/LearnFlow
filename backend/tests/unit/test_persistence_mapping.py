"""Tests for the curriculum persistence mapping.

These compile DDL for the PostgreSQL dialect rather than executing it, so they
need no database and stay in the unit suite. They guard the properties the
initial migration was hand-written against: table and constraint names, the two
constraints whose behaviour depends on a PostgreSQL-specific clause, and the
column types docs/database/schema.md specifies.

Whether the migration and these models actually agree is settled against a live
database by tests/integration/test_curriculum_migration.py.
"""

import uuid

import pytest
from sqlalchemy import Boolean, DateTime, Integer, Uuid
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

CURRICULUM_TABLES = (
    "learning_programs",
    "curriculum_versions",
    "subjects",
    "topics",
    "topic_relationships",
)


def compiled(table_name: str) -> str:
    """Render CREATE TABLE for the PostgreSQL dialect."""
    return str(CreateTable(Base.metadata.tables[table_name]).compile(dialect=postgresql.dialect()))


def constraint_names(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {constraint.name for constraint in table.constraints if constraint.name}


def test_only_the_curriculum_tables_are_mapped():
    """Learner, resource, and assessment tables arrive with their milestones."""
    assert set(Base.metadata.tables) == set(CURRICULUM_TABLES)


@pytest.mark.parametrize("table_name", CURRICULUM_TABLES)
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
    for table_name in CURRICULUM_TABLES:
        for column in Base.metadata.tables[table_name].columns:
            if isinstance(column.type, DateTime) and not column.type.timezone:
                naive.append(f"{table_name}.{column.name}")

    assert naive == []


@pytest.mark.parametrize("table_name", CURRICULUM_TABLES)
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


def test_learner_owned_tables_are_absent():
    """Guards the agreed scope: this change is the curriculum foundation only."""
    for table_name in ("learners", "study_goals", "learner_topic_progress"):
        assert table_name not in Base.metadata.tables
