"""Persistence models for the learner, their goal, and when they can study.

Implements the first three tables of the *Learner planning* schema area of
docs/database/schema.md:

    learners -> study_goals -> availability_slots
                            -> curriculum_versions / examination_schedules

`study_plans` and `plan_items` are deliberately absent. Each arrives with the
planning code that reads it, per ADR-011, so no column fixes a shape before a
requirement constrains it.

`study_goals.target_date` is nullable here, where docs/database/schema.md first
described it as a plain date. A learner preparing for a published examination
aims at a *window* whose specific paper day the examining body has not yet
announced; storing one date would record a guess as the learner's deadline. A
goal therefore points at an examination schedule, carries a target date, or
both, and a CHECK refuses a goal that carries neither.

`availability_slots.day_of_week` is `snake_case` text rather than the smallint
docs/database/schema.md first described, and ADR-018 records why: every other
controlled value in this schema is validated text guarded by a CHECK (ADR-011),
and a stored day *name* leaves no numbering convention for a reader or a client
to get wrong. There is no ordering column: the week's order is a fixed list in
the application, because Monday-first is presentation rather than data.
"""

import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import (
    Base,
    TimestampMixin,
    UuidPrimaryKeyMixin,
    in_clause,
)

STUDY_GOAL_STATUSES = ("active", "paused", "completed", "archived")

WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
"""The seven days `availability_slots.day_of_week` accepts, in week order.

Stored as the `snake_case` value, which is also what goes on the wire: there is
no numbering convention to document, and therefore none to mis-map. The order
here is the order a week is shown in, not a stored rank.
"""

MINUTES_IN_A_DAY = 24 * 60
"""Upper bound on `available_minutes`. A day cannot hold more study than it has."""


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


class AvailabilitySlot(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """How much study time one goal has on one day of the week.

    Availability belongs to the goal rather than to the learner: a learner who
    archives one goal and starts another is describing a different week, and
    docs/database/schema.md attaches the row to `study_goals` for that reason.

    A day with no row here is a day the learner has not set. A row carrying
    zero minutes is a day they deliberately marked unavailable -- the same
    distinction `learner_topic_progress` draws between no record and an explicit
    `not_explored`, and the reason the approved constraint is `>= 0` rather than
    `> 0`.
    """

    __tablename__ = "availability_slots"

    study_goal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_goals.id"), nullable=False)
    day_of_week: Mapped[str] = mapped_column(String(16), nullable=False)
    available_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        # One row per goal and day, which is what makes saving a week a rewrite
        # of the days it names rather than an append beside them.
        UniqueConstraint("study_goal_id", "day_of_week"),
        CheckConstraint(
            in_clause("day_of_week", WEEKDAYS),
            name="day_of_week_is_known",
        ),
        # docs/database/schema.md approves the lower bound. The upper bound is
        # added here because a day holds 1440 minutes, so a larger value is
        # always a mistake rather than an ambitious learner.
        CheckConstraint(
            f"available_minutes >= 0 AND available_minutes <= {MINUTES_IN_A_DAY}",
            name="available_minutes_within_a_day",
        ),
    )
