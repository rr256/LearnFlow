"""create availability slots table

Creates the third table of the *Learner planning* schema area of
docs/database/schema.md, ``availability_slots``. ``study_plans`` and
``plan_items`` remain absent and arrive with Milestone 3's planning code, per
ADR-011.

``day_of_week`` is ``varchar(16)`` holding ``monday`` to ``sunday``, not the
``smallint`` docs/database/schema.md first described. ADR-018 records why: every
other controlled value in this schema is validated text guarded by a CHECK
(ADR-011), and a stored day *name* leaves no numbering convention to document or
to mis-map. This is what closes the last of the three open items ADR-011 recorded
for the project owner.

``available_minutes`` carries the lower bound docs/database/schema.md approves
and an upper bound of 1440 it does not: a day holds 1440 minutes, so a larger
value is always a mistake. Zero is deliberately accepted -- a day the learner
marked unavailable, distinct from a day they never set, which has no row at all.

Constraint names follow the convention on ``Base.metadata``. Primary, unique, and
foreign-key conventions ignore a supplied name, so those are written out in full;
the check convention interpolates the supplied name, so a check passes only its
distinguishing suffix.

Revision ID: 20260806_01
Revises: 20260805_01
Created: 2026-08-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260806_01"
down_revision: str | None = "20260805_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "availability_slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("study_goal_id", sa.Uuid(), nullable=False),
        sa.Column("day_of_week", sa.String(length=16), nullable=False),
        sa.Column("available_minutes", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_availability_slots"),
        sa.ForeignKeyConstraint(
            ["study_goal_id"],
            ["study_goals.id"],
            name="fk_availability_slots_study_goal_id_study_goals",
        ),
        # One row per goal and day. Saving a week therefore rewrites the days it
        # names rather than appending a second Monday beside the first, and it is
        # what makes the unique key a client can address a day by.
        sa.UniqueConstraint(
            "study_goal_id",
            "day_of_week",
            name="uq_availability_slots_study_goal_id_day_of_week",
        ),
        sa.CheckConstraint(
            "day_of_week IN ('monday', 'tuesday', 'wednesday', 'thursday', "
            "'friday', 'saturday', 'sunday')",
            name="day_of_week_is_known",
        ),
        sa.CheckConstraint(
            "available_minutes >= 0 AND available_minutes <= 1440",
            name="available_minutes_within_a_day",
        ),
    )
    # No further index. The unique constraint creates one on
    # `(study_goal_id, day_of_week)`, whose leading column serves the only read
    # there is: every slot belonging to one goal. docs/database/schema.md lists
    # none for this table under Required Indexes.


def downgrade() -> None:
    # This table holds learner-owned data. Dropping it is safe only while it is
    # new and empty in every environment that has it; once a learner has recorded
    # a week, reverting this migration destroys it. A later migration touching
    # the populated table needs the staged approach in
    # docs/database/migrations.md rather than a drop.
    op.drop_table("availability_slots")
