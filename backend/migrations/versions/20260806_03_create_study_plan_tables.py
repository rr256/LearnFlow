"""create study plan tables

Completes the *Learner planning* schema area of docs/database/schema.md by
creating its last two tables, ``study_plans`` and ``plan_items``. Both arrive with
the planning code that reads them, which is the ordering ADR-011 prescribes: this
migration and the use case behind PLN-001 to PLN-003 travel together.

``plan_type``, ``status``, and ``action_type`` are ``varchar(32)`` guarded by a
CHECK rather than the bare ``text`` docs/database/schema.md describes. ADR-020
records the departure, which is the one ADR-018 made for ``day_of_week`` and
ADR-019 for ``topic_sequencing``, and for the same reason: every other controlled
value in this schema is validated text, and a controlled value with nothing but
application code between it and the row is one typo from being stored and trusted.

Both indexes are the ones docs/database/schema.md lists under *Required Indexes*
for these tables. ``estimated_minutes > 0`` is the constraint it approves, written
with an explicit NULL branch because the column is nullable.

Constraint names follow the convention on ``Base.metadata``. Primary, unique, and
foreign-key conventions ignore a supplied name, so those are written out in full;
the check convention interpolates the supplied name, so a check passes only its
distinguishing suffix.

Revision ID: 20260806_03
Revises: 20260806_02
Created: 2026-08-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260806_03"
down_revision: str | None = "20260806_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "study_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("study_goal_id", sa.Uuid(), nullable=False),
        sa.Column("plan_type", sa.String(length=32), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("generation_reason", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_study_plans"),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_study_plans_learner_id_learners",
        ),
        sa.ForeignKeyConstraint(
            ["study_goal_id"],
            ["study_goals.id"],
            name="fk_study_plans_study_goal_id_study_goals",
        ),
        sa.CheckConstraint(
            "plan_type IN ('roadmap', 'monthly', 'weekly', 'daily')",
            name="plan_type_is_known",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'superseded', 'archived')",
            name="status_is_known",
        ),
    )
    op.create_index(
        "ix_study_plans_learner_id_study_goal_id_status_period_start",
        "study_plans",
        ["learner_id", "study_goal_id", "status", "period_start"],
    )

    op.create_table(
        "plan_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("study_plan_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=True),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("scheduled_for", sa.Date(), nullable=True),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("recommendation_reason", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_plan_items"),
        sa.ForeignKeyConstraint(
            ["study_plan_id"],
            ["study_plans.id"],
            name="fk_plan_items_study_plan_id_study_plans",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name="fk_plan_items_topic_id_topics",
        ),
        sa.CheckConstraint(
            "action_type IN ('study', 'practice', 'revise', 'review_mistakes')",
            name="action_type_is_known",
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'completed', 'skipped', 'postponed')",
            name="status_is_known",
        ),
        sa.CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes > 0",
            name="estimated_minutes_is_positive",
        ),
    )
    op.create_index(
        "ix_plan_items_study_plan_id_scheduled_for_status",
        "plan_items",
        ["study_plan_id", "scheduled_for", "status"],
    )


def downgrade() -> None:
    # These tables hold learner-owned data. Dropping them is safe only while they
    # are new and empty in every environment that has them; once a learner has a
    # plan, reverting this migration destroys it along with whatever they had
    # already completed. A later migration touching a populated table needs the
    # staged approach in docs/database/migrations.md rather than a drop.
    #
    # Items first: they reference the plans. No constraint is named -- dropping a
    # table takes its checks and indexes with it, which also keeps the downgrade
    # clear of the `ck` naming convention that bit revision 20260806_02.
    op.drop_table("plan_items")
    op.drop_table("study_plans")
