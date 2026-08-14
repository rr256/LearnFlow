"""create revision records table

Adds ``revision_records`` to the *Progress and revision* schema area of
docs/database/schema.md, beside ``learner_topic_progress``. It arrives with the
revision code that reads it, which is the ordering ADR-011 prescribes: this
migration and the use case behind REV-001 to REV-004 travel together.

**Additive.** One CREATE TABLE and one index; no existing table is altered and no
stored row is read, rewritten, or reinterpreted. A learner with plans, items,
completions, and progress keeps every one of them untouched, and the new table
starts empty because a revision is created only when the learner asks for one.

``status`` and ``trigger_type`` are ``varchar(32)`` guarded by a CHECK rather
than the bare ``text`` docs/database/schema.md describes, following its own
*Conventions*, ADR-011's validated-text rule, and the precedent ``day_of_week``,
``topic_sequencing``, and the study-plan columns each set.

``recommendation_reason`` is a column docs/database/schema.md's table does not
list. ADR-028 records the departure: a revision's due date is computed from the
learning stage recorded at the moment it was created, so a reason recomputed
later from a stage the learner has since changed would contradict the date stored
beside it. Freezing the sentence keeps the record self-explaining, which is the
same guarantee ``plan_items.recommendation_reason`` carries.

``scheduled_for`` is created and left unwritten, as is the ``scheduled`` status
the CHECK permits. Naming a day for a revision is a second capability, and the
constraint carries the value so it arrives as a use-case change rather than a
migration — the argument ADR-020 made for ``plan_items.status``.

The index is the one docs/database/schema.md lists under *Required Indexes* for
this table.

Constraint names follow the convention on ``Base.metadata``. Primary, unique, and
foreign-key conventions ignore a supplied name, so those are written out in full;
the check convention interpolates the supplied name, so a check passes only its
distinguishing suffix.

Revision ID: 20260813_01
Revises: 20260806_03
Created: 2026-08-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_01"
down_revision: str | None = "20260806_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVISION_STATUSES = ("due", "scheduled", "completed", "skipped", "postponed")
REVISION_TRIGGERS = ("completed_plan_item", "completed_revision")


def _in_clause(column: str, allowed: tuple[str, ...]) -> str:
    """Render the membership test the model builds for the same column.

    Written out here rather than imported: a migration describes the schema at
    one moment in history and must keep applying after the application constant
    it mirrors has moved on.
    """
    values = ", ".join(f"'{value}'" for value in allowed)
    return f"{column} IN ({values})"


def upgrade() -> None:
    """Create ``revision_records`` and its index."""
    op.create_table(
        "revision_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("plan_item_id", sa.Uuid(), nullable=True),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("scheduled_for", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_revision_records"),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_revision_records_learner_id_learners",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name="fk_revision_records_topic_id_topics",
        ),
        # Not a cascade. A plan item lives on a plan that adaptation supersedes,
        # and a revision the learner has acted on must outlive that.
        sa.ForeignKeyConstraint(
            ["plan_item_id"],
            ["plan_items.id"],
            name="fk_revision_records_plan_item_id_plan_items",
        ),
        sa.CheckConstraint(_in_clause("status", REVISION_STATUSES), name="status_is_known"),
        sa.CheckConstraint(
            _in_clause("trigger_type", REVISION_TRIGGERS), name="trigger_type_is_known"
        ),
    )
    op.create_index(
        "ix_revision_records_learner_id_due_on_status",
        "revision_records",
        ["learner_id", "due_on", "status"],
    )


def downgrade() -> None:
    """Drop the table, and the index with it.

    The index is dropped explicitly before the table for symmetry with the
    upgrade. No constraint is named: dropping a table takes its checks with it,
    which also keeps this clear of the ``ck`` naming convention that bit revision
    ``20260806_02``. See docs/database/migrations.md.
    """
    op.drop_index("ix_revision_records_learner_id_due_on_status", table_name="revision_records")
    op.drop_table("revision_records")
