"""create examination schedule and learner goal tables

Creates the *Examination schedule* schema area of docs/database/schema.md --
``examination_schedules`` and ``examination_periods`` -- and the first two tables
of the *Learner planning* area, ``learners`` and ``study_goals``.

The examination is stored as dated periods rather than one column. An examining
body publishes a range of sitting days and names the specific paper's day much
later, so a single date column could hold only a guess.

``study_goals.target_date`` is nullable, which docs/database/schema.md first
described as a plain date. A goal aims at a published examination cycle, at a
target completion date, or at both; ``ck_study_goals_aims_at_a_date_or_an_examination``
refuses one that aims at neither. Nullable is safe to add here because the table
is created empty by this same migration.

``availability_slots``, ``study_plans``, and ``plan_items`` remain absent, as do
``study_goals.planning_preferences``. Each arrives with the planning code that
reads it, per ADR-011, so no column fixes a convention before a requirement
constrains it.

Constraint names follow the convention on ``Base.metadata``. Primary, unique,
foreign-key, and index conventions ignore a supplied name, so those are written
out in full; the check convention interpolates the supplied name, so a check
passes only its distinguishing suffix.

Revision ID: 20260801_01
Revises: 20260731_02
Created: 2026-08-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_01"
down_revision: str | None = "20260731_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "examination_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learning_program_id", sa.Uuid(), nullable=False),
        sa.Column("cycle_label", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("organising_body", sa.Text(), nullable=True),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("source_checked_on", sa.Date(), nullable=False),
        sa.Column("schedule_status", sa.String(length=32), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_examination_schedules"),
        sa.ForeignKeyConstraint(
            ["learning_program_id"],
            ["learning_programs.id"],
            name="fk_examination_schedules_learning_program_id_learning_programs",
        ),
        sa.UniqueConstraint(
            "learning_program_id",
            "cycle_label",
            name="uq_examination_schedules_learning_program_id_cycle_label",
        ),
        sa.CheckConstraint(
            "schedule_status IN ('provisional', 'confirmed')",
            name="schedule_status_is_known",
        ),
    )

    op.create_table(
        "examination_periods",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("examination_schedule_id", sa.Uuid(), nullable=False),
        sa.Column("period_type", sa.String(length=32), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_examination_periods"),
        # These two names abbreviate the `examination_schedule_id` segment to
        # `schedule_id`. The full convention name runs to 68 characters, past
        # PostgreSQL's 63-character identifier limit, and a truncated name is one
        # a downgrade could not drop. The models name them identically.
        sa.ForeignKeyConstraint(
            ["examination_schedule_id"],
            ["examination_schedules.id"],
            name="fk_examination_periods_schedule_id_examination_schedules",
        ),
        # A cycle can hold several periods of one type -- GATE 2027 is sat over
        # three separate weekends -- so the type alone does not identify a
        # period, but a type and a start date do. This is the seed's natural key.
        sa.UniqueConstraint(
            "examination_schedule_id",
            "period_type",
            "starts_on",
            name="uq_examination_periods_schedule_id_period_type_starts_on",
        ),
        sa.CheckConstraint(
            "period_type IN ('registration', 'late_registration', 'examination', 'results')",
            name="period_type_is_known",
        ),
        # A single-day event stores the same date twice, so this is `>=`.
        sa.CheckConstraint(
            "ends_on >= starts_on",
            name="ends_on_is_not_before_starts_on",
        ),
    )

    op.create_index(
        "ix_examination_periods_examination_schedule_id_starts_on",
        "examination_periods",
        ["examination_schedule_id", "starts_on"],
    )

    op.create_table(
        "learners",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_learners"),
    )

    op.create_table(
        "study_goals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("learning_program_id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_version_id", sa.Uuid(), nullable=False),
        sa.Column("examination_schedule_id", sa.Uuid(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_study_goals"),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_study_goals_learner_id_learners",
        ),
        sa.ForeignKeyConstraint(
            ["learning_program_id"],
            ["learning_programs.id"],
            name="fk_study_goals_learning_program_id_learning_programs",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_version_id"],
            ["curriculum_versions.id"],
            name="fk_study_goals_curriculum_version_id_curriculum_versions",
        ),
        sa.ForeignKeyConstraint(
            ["examination_schedule_id"],
            ["examination_schedules.id"],
            name="fk_study_goals_examination_schedule_id_examination_schedules",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'completed', 'archived')",
            name="status_is_known",
        ),
        sa.CheckConstraint(
            "target_date IS NOT NULL OR examination_schedule_id IS NOT NULL",
            name="aims_at_a_date_or_an_examination",
        ),
    )


def downgrade() -> None:
    # Reverse creation order so no foreign key outlives the table it points at.
    #
    # `study_goals` and `learners` hold learner-owned data. This downgrade drops
    # it, which is safe only while the tables are new and empty in every
    # environment that has them. Once a learner has recorded a goal, reverting
    # this migration destroys it; a later migration touching populated tables
    # needs the staged approach in docs/database/migrations.md.
    op.drop_table("study_goals")
    op.drop_table("learners")
    op.drop_index(
        "ix_examination_periods_examination_schedule_id_starts_on",
        table_name="examination_periods",
    )
    op.drop_table("examination_periods")
    op.drop_table("examination_schedules")
