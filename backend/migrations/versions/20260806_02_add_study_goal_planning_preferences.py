"""add study goal planning preferences

Adds the learner's planning preferences to ``study_goals``, completing the
*Learner planning* schema area's goal table. ``study_plans`` and ``plan_items``
remain absent and arrive with Milestone 3's planning code, per ADR-011.

Two typed nullable columns rather than the ``planning_preferences jsonb``
docs/database/schema.md first described. ADR-019 records why: that document
reserves ``jsonb`` for flexible provider and resource payloads rather than core
relational concepts, and no CHECK can guard a key inside JSON -- so a controlled
value stored that way would carry exactly the silent mis-mapping risk ADR-018
removed from ``day_of_week``. This is the same kind of departure from a
documented target that ADR-018 made, and it is recorded against the table in
schema.md.

``preferred_session_minutes`` is a **duration**, not a time of day. It does not
reopen ADR-018's deliberate refusal to store clock times; a session length is the
same kind of value as ``available_minutes``.

Both columns are nullable with **no database default**, which is what keeps a
preference the learner never set distinguishable from one the product guessed for
them -- the distinction ADR-017 drew between an explicit ``not_explored`` and no
record at all, and ADR-018 drew between zero minutes and no row.

This is the additive change docs/database/migrations.md prefers: two nullable
columns on an existing table, needing no backfill and reinterpreting no stored
value. Every goal already stored reads back with no preferences set, which is
true of it.

Constraint names follow the convention on ``Base.metadata``; the check convention
interpolates the supplied name, so each check passes only its distinguishing
suffix.

Revision ID: 20260806_02
Revises: 20260806_01
Created: 2026-08-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260806_02"
down_revision: str | None = "20260806_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "study_goals",
        sa.Column("preferred_session_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "study_goals",
        sa.Column("topic_sequencing", sa.String(length=32), nullable=True),
    )
    # `IS NULL OR` is written out rather than left to three-valued CHECK
    # semantics, which pass on NULL anyway. A reader should not need to recall
    # that to see that an unset preference is permitted.
    op.create_check_constraint(
        "preferred_session_minutes_within_bounds",
        "study_goals",
        "preferred_session_minutes IS NULL OR (preferred_session_minutes >= 15 "
        "AND preferred_session_minutes <= 480)",
    )
    op.create_check_constraint(
        "topic_sequencing_is_known",
        "study_goals",
        "topic_sequencing IS NULL OR topic_sequencing IN ('syllabus_order', 'prerequisites_first')",
    )
    # No index. Nothing filters or orders goals by a preference: a preference is
    # read as part of the goal that owns it, which is already addressed by its
    # primary key. docs/database/schema.md lists none for `study_goals`.


def downgrade() -> None:
    # These columns hold learner-owned data. Dropping them is safe only while
    # they are new and unset in every environment that has them; once a learner
    # has recorded a preference, reverting this migration destroys it. Constraints
    # are dropped before the columns they guard, because dropping a column would
    # otherwise leave the check referring to a column that is gone.
    op.drop_constraint("ck_study_goals_topic_sequencing_is_known", "study_goals", type_="check")
    op.drop_constraint(
        "ck_study_goals_preferred_session_minutes_within_bounds", "study_goals", type_="check"
    )
    op.drop_column("study_goals", "topic_sequencing")
    op.drop_column("study_goals", "preferred_session_minutes")
