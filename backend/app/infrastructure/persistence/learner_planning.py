"""Persistence models for the learner and the goal they are studying toward.

Implements the first two tables of the *Learner planning* schema area of
docs/database/schema.md:

    learners -> study_goals -> curriculum_versions / examination_schedules

`availability_slots`, `study_plans`, and `plan_items` are deliberately absent.
Each arrives with the planning code that reads it, per ADR-011, so no column
fixes a convention -- the `day_of_week` numbering above all -- before a
requirement constrains it.

`study_goals.target_date` is nullable here, where docs/database/schema.md first
described it as a plain date. A learner preparing for a published examination
aims at a *window* whose specific paper day the examining body has not yet
announced; storing one date would record a guess as the learner's deadline. A
goal therefore points at an examination schedule, carries a target date, or
both, and a CHECK refuses a goal that carries neither.
"""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import (
    Base,
    TimestampMixin,
    UuidPrimaryKeyMixin,
    in_clause,
)

STUDY_GOAL_STATUSES = ("active", "paused", "completed", "archived")


class Learner(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """A person using LearnFlow, and their local preferences.

    The MVP has one, but every learner-owned record carries `learner_id` from the
    start so multiple accounts stay a matter of authentication rather than a
    migration touching every table.
    """

    __tablename__ = "learners"

    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    # An IANA zone name such as `Asia/Kolkata`; the longest in the database is
    # comfortably inside 64. Supplied by the composition root from
    # APP_DEFAULT_TIMEZONE, never defaulted here: a timestamp interpreted in the
    # wrong zone is wrong by a day at the boundary, which is exactly where a
    # study plan's dates land.
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)


class StudyGoal(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """What one learner is studying, and what they are working toward."""

    __tablename__ = "study_goals"

    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    learning_program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_programs.id"), nullable=False
    )
    curriculum_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_versions.id"), nullable=False
    )
    # A reference, not a copy of the dates. A schedule the examining body revises
    # then reaches every goal pointing at it, and no goal can drift from the
    # published source.
    examination_schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("examination_schedules.id"), nullable=True
    )
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        CheckConstraint(
            in_clause("status", STUDY_GOAL_STATUSES),
            name="status_is_known",
        ),
        # A goal must aim at something. Both columns are nullable so that a
        # learner preparing for an examination need not invent a date and a
        # learner following none need not invent a cycle, but a goal with
        # neither has no horizon to plan against.
        CheckConstraint(
            "target_date IS NOT NULL OR examination_schedule_id IS NOT NULL",
            name="aims_at_a_date_or_an_examination",
        ),
    )
