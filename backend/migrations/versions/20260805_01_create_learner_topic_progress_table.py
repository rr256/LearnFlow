"""create learner topic progress table

Creates the first table of the *Progress and revision* schema area of
docs/database/schema.md, ``learner_topic_progress``.

The area is created **partially**. Three columns docs/database/schema.md holds as
an approved target are deliberately not created here:

- ``material_status`` and ``material_completed_at``, which belong to material
  completion. Nothing records it yet.
- ``last_studied_at``, which can only be filled from a study activity.
  ``study_activities`` does not exist.

Each arrives with the change that writes it, per ADR-011: a column created before
the code maintaining it fixes a shape no requirement has yet constrained. Adding
a nullable column to this table later is an additive migration, which
docs/database/migrations.md prefers. ``revision_records`` arrives with Milestone
3.

``stage_source`` **is** created, though every row written today says ``learner``.
It distinguishes a stage the learner chose from one derived later from quiz or
external-test evidence; adding it afterwards would mean backfilling rows whose
origin is no longer recoverable. See ADR-017.

Constraint names follow the convention on ``Base.metadata``. Primary, unique, and
foreign-key conventions ignore a supplied name, so those are written out in full;
the check convention interpolates the supplied name, so a check passes only its
distinguishing suffix.

Revision ID: 20260805_01
Revises: 20260801_01
Created: 2026-08-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_01"
down_revision: str | None = "20260801_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learner_topic_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("learning_stage", sa.String(length=32), nullable=False),
        sa.Column("stage_source", sa.String(length=16), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_learner_topic_progress"),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_learner_topic_progress_learner_id_learners",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name="fk_learner_topic_progress_topic_id_topics",
        ),
        # One record per learner and topic. This is what makes recording a stage
        # an update of the existing row rather than a second row alongside it,
        # and it is the unique index schema.md lists under Required Indexes.
        sa.UniqueConstraint(
            "learner_id",
            "topic_id",
            name="uq_learner_topic_progress_learner_id_topic_id",
        ),
        sa.CheckConstraint(
            "learning_stage IN ('not_explored', 'building_foundation', "
            "'developing_confidence', 'practice_ready', 'strong_understanding')",
            name="learning_stage_is_known",
        ),
        sa.CheckConstraint(
            "stage_source IN ('learner', 'derived', 'mixed')",
            name="stage_source_is_known",
        ),
    )


def downgrade() -> None:
    # This table holds learner-owned data. Dropping it is safe only while it is
    # new and empty in every environment that has it; once a learner has recorded
    # a stage, reverting this migration destroys that record. A later migration
    # touching the populated table needs the staged approach in
    # docs/database/migrations.md rather than a drop.
    op.drop_table("learner_topic_progress")
