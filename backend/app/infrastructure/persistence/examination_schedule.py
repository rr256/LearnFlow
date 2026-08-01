"""Persistence models for published examination schedules.

Implements the *Examination schedule* schema area of docs/database/schema.md:

    learning_programs -> examination_schedules -> examination_periods

This is reference data, not learner data. One row describes what an examining
body has published for one cycle of a learning program -- GATE 2027, say -- and
every learner planning against that cycle reads the same dates.

The examination is stored as one or more dated periods rather than a single
column, because examining bodies publish a range of sitting days and announce
the specific paper's day much later. A period whose start and end are the same
day is a single-day event, which is how a results announcement is stored.

`schedule_status` is the "liable to change" flag the sources themselves carry: a
schedule stays `provisional` until the examining body confirms its dates. Like
every other controlled value it is text guarded by a CHECK rather than a
PostgreSQL enum (ADR-011).
"""

import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
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

EXAMINATION_SCHEDULE_STATUSES = ("provisional", "confirmed")
EXAMINATION_PERIOD_TYPES = (
    "registration",
    "late_registration",
    "examination",
    "results",
)


class ExaminationSchedule(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """The calendar an examining body publishes for one cycle of a program."""

    __tablename__ = "examination_schedules"

    learning_program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_programs.id"), nullable=False
    )
    cycle_label: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    organising_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # NOT NULL, unlike `curriculum_versions.source_reference`. A schedule exists
    # only because a source published it, and a stored date with no traceable
    # origin cannot be checked when the examining body revises it.
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    source_checked_on: Mapped[date] = mapped_column(Date, nullable=False)
    schedule_status: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint("learning_program_id", "cycle_label"),
        CheckConstraint(
            in_clause("schedule_status", EXAMINATION_SCHEDULE_STATUSES),
            name="schedule_status_is_known",
        ),
    )


class ExaminationPeriod(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """One dated period of a schedule: registration, the examination, or the result.

    Two constraints here are named explicitly, against the usual practice of
    letting the convention on ``Base.metadata`` generate them. The generated
    names -- built from this table plus the full ``examination_schedule_id``
    column -- run to 68 characters, past PostgreSQL's 63-character identifier
    limit, and SQLAlchemy would silently truncate them to a hashed form the
    migration could not reproduce. The names below abbreviate that one segment to
    ``schedule_id`` and otherwise follow the convention exactly.
    """

    __tablename__ = "examination_periods"

    examination_schedule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "examination_schedules.id",
            name="fk_examination_periods_schedule_id_examination_schedules",
        ),
        nullable=False,
    )
    period_type: Mapped[str] = mapped_column(String(32), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        # The seed's natural key. A cycle can hold several periods of one type --
        # GATE 2027 is sat over three separate weekends -- so the type alone does
        # not identify a period, but a type and a start date do.
        UniqueConstraint(
            "examination_schedule_id",
            "period_type",
            "starts_on",
            name="uq_examination_periods_schedule_id_period_type_starts_on",
        ),
        CheckConstraint(
            in_clause("period_type", EXAMINATION_PERIOD_TYPES),
            name="period_type_is_known",
        ),
        # A single-day event stores the same date twice, so this is `>=`, not `>`.
        CheckConstraint(
            "ends_on >= starts_on",
            name="ends_on_is_not_before_starts_on",
        ),
        # Reading a schedule in date order is how both the seed and a goal read
        # it; no other access pattern exists yet.
        Index(None, "examination_schedule_id", "starts_on"),
    )
