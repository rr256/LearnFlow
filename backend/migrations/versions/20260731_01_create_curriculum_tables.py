"""create curriculum tables

Creates the curriculum hierarchy from the *Curriculum* schema area of
docs/database/schema.md: learning programs, their versioned curricula, subjects,
topics with optional nesting, and prerequisite/sequencing relationships between
topics.

Learner planning, progress, resource, and assessment tables are deliberately
absent. Each arrives with the milestone that uses it, so no table exists before
the code and constraints that give it meaning.

Constraint names come from the naming convention on ``Base.metadata``, which
``migrations/env.py`` hands to Alembic as ``target_metadata`` in both online and
offline mode. The two families behave differently and are written accordingly:

* Primary, unique, foreign-key, and index conventions ignore a supplied name, so
  those are written out in full here.
* The check convention is ``ck_%(table_name)s_%(constraint_name)s`` -- it
  interpolates the supplied name -- so a check passes only its distinguishing
  suffix. Passing the full name would prefix it twice and overrun PostgreSQL's
  63-character identifier limit, leaving a hash-truncated name.

Revision ID: 20260731_01
Revises:
Created: 2026-07-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260731_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_programs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_learning_programs"),
        sa.UniqueConstraint("code", name="uq_learning_programs_code"),
    )

    op.create_table(
        "curriculum_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learning_program_id", sa.Uuid(), nullable=False),
        sa.Column("version_label", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_curriculum_versions"),
        sa.ForeignKeyConstraint(
            ["learning_program_id"],
            ["learning_programs.id"],
            name="fk_curriculum_versions_learning_program_id_learning_programs",
        ),
        sa.UniqueConstraint(
            "learning_program_id",
            "version_label",
            name="uq_curriculum_versions_learning_program_id_version_label",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'retired')",
            name="status_is_known",
        ),
    )

    # At most one active version per learning program. A partial unique index is
    # the only form that expresses "unique among the active rows only", leaving
    # any number of draft and retired versions alongside it.
    op.create_index(
        "uq_curriculum_versions_active_learning_program_id",
        "curriculum_versions",
        ["learning_program_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "subjects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_version_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_subjects"),
        sa.ForeignKeyConstraint(
            ["curriculum_version_id"],
            ["curriculum_versions.id"],
            name="fk_subjects_curriculum_version_id_curriculum_versions",
        ),
        sa.UniqueConstraint(
            "curriculum_version_id",
            "code",
            name="uq_subjects_curriculum_version_id_code",
        ),
        sa.UniqueConstraint(
            "curriculum_version_id",
            "position",
            name="uq_subjects_curriculum_version_id_position",
        ),
    )

    op.create_table(
        "topics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("parent_topic_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_trackable", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_topics"),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name="fk_topics_subject_id_subjects",
        ),
        sa.ForeignKeyConstraint(
            ["parent_topic_id"],
            ["topics.id"],
            name="fk_topics_parent_topic_id_topics",
        ),
        # NULLS NOT DISTINCT requires PostgreSQL 15 or later. Without it, root
        # topics -- every one of which has a NULL parent -- would escape the
        # constraint entirely, because PostgreSQL treats each NULL as distinct.
        sa.UniqueConstraint(
            "subject_id",
            "parent_topic_id",
            "name",
            name="uq_topics_subject_id_parent_topic_id_name",
            postgresql_nulls_not_distinct=True,
        ),
    )

    op.create_index(
        "ix_topics_subject_id_parent_topic_id_position",
        "topics",
        ["subject_id", "parent_topic_id", "position"],
    )

    op.create_table(
        "topic_relationships",
        sa.Column("source_topic_id", sa.Uuid(), nullable=False),
        sa.Column("target_topic_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "source_topic_id",
            "target_topic_id",
            "relationship_type",
            name="pk_topic_relationships",
        ),
        sa.ForeignKeyConstraint(
            ["source_topic_id"],
            ["topics.id"],
            name="fk_topic_relationships_source_topic_id_topics",
        ),
        sa.ForeignKeyConstraint(
            ["target_topic_id"],
            ["topics.id"],
            name="fk_topic_relationships_target_topic_id_topics",
        ),
        sa.CheckConstraint(
            "relationship_type IN ('prerequisite', 'recommended_before', 'related')",
            name="relationship_type_is_known",
        ),
        sa.CheckConstraint(
            "source_topic_id <> target_topic_id",
            name="source_and_target_differ",
        ),
    )


def downgrade() -> None:
    # Reverse creation order so no foreign key outlives the table it points at.
    #
    # This downgrade is safe only because these tables are reference data that
    # no learner record yet points to. Once curriculum rows carry learner
    # progress, dropping them destroys that history; a later migration touching
    # populated tables needs the staged approach in docs/database/migrations.md.
    op.drop_table("topic_relationships")
    op.drop_index("ix_topics_subject_id_parent_topic_id_position", table_name="topics")
    op.drop_table("topics")
    op.drop_table("subjects")
    op.drop_index(
        "uq_curriculum_versions_active_learning_program_id",
        table_name="curriculum_versions",
    )
    op.drop_table("curriculum_versions")
    op.drop_table("learning_programs")
