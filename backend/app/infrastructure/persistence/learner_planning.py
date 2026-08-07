"""Persistence models for the learner, their goal, when they can study, and the plan.

Implements the whole *Learner planning* schema area of docs/database/schema.md:

    learners -> study_goals -> availability_slots
                            -> study_plans -> plan_items
                            -> curriculum_versions / examination_schedules

`study_plans` and `plan_items` arrive with the planning code that reads them, per
ADR-011 — which is this change. `plan_type`, `status`, and `action_type` are
`varchar(32)` guarded by a CHECK rather than the bare `text` that document's table
describes, following its own *Conventions*, ADR-011's validated-text rule, and the
precedent `day_of_week` and `topic_sequencing` set; ADR-020 records the departure.

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

`study_goals` carries the learner's planning preferences as two typed nullable
columns rather than the `planning_preferences jsonb` docs/database/schema.md
first described, and ADR-019 records why: `jsonb` is reserved there for flexible
provider and resource payloads, and no CHECK can guard a key inside one, so a
controlled value stored that way would have exactly the mis-mapping problem
ADR-018 removed from `day_of_week`. Both are nullable with no database default,
so a preference the learner has not set stays distinguishable from one the
product guessed for them.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
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

TOPIC_SEQUENCING_CHOICES = ("syllabus_order", "prerequisites_first")
"""The orders `study_goals.topic_sequencing` accepts.

Stored as the `snake_case` value, which is also what goes on the wire. Both are
derivable from tables that exist: `syllabus_order` from the stored `position` of
subjects and topics, `prerequisites_first` from the `prerequisite` edges in
`topic_relationships`.
"""

MINIMUM_SESSION_MINUTES = 15
MAXIMUM_SESSION_MINUTES = 480
"""Bounds on `preferred_session_minutes`, mirroring the database CHECK.

A quarter of an hour is the shortest block that holds study rather than overhead;
eight hours is a full working day, and a day is already bounded by its
availability. A duration, not a time of day -- nothing here stores when in a day
a session falls.
"""

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

PLAN_TYPES = ("roadmap", "monthly", "weekly", "daily")
"""The plan types `study_plans.plan_type` accepts, all four approved by DEC-021.

Two are written today: a `roadmap` ordering the whole curriculum and a `weekly`
plan dating the topics the coming week has room for. `monthly` and `daily` are
constrained now so adding one stays a use-case change rather than a migration.
"""

PLAN_STATUSES = ("draft", "active", "superseded", "archived")
"""The statuses `study_plans.status` accepts.

Generating a plan writes `active` and moves what it replaces to `superseded`,
because docs/database/schema.md asks that plans be superseded rather than deleted
so a learner's plan history stays explainable.
"""

PLAN_ITEM_ACTIONS = ("study", "practice", "revise", "review_mistakes")
"""The actions `plan_items.action_type` accepts.

Every item written today is `study`. The other three name work the product does
not model yet -- practice needs checkpoint quizzes, revision needs revision
records, mistake review needs mistake evidence -- so nothing writes them.
"""

PLAN_ITEM_STATUSES = ("planned", "completed", "skipped", "postponed")
"""The statuses `plan_items.status` accepts.

Every item is written `planned` and stays there: moving one is PLN-004's work,
which belongs to FR-004 and is not implemented. The column exists because an item
without a state is not a plan item, and because the alternative -- adding it once
learners have plans -- means backfilling rows whose state nobody recorded.
"""


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
    # The learner's planning preferences. Nullable with no database default, so a
    # preference nobody set never reads as one somebody chose: a planner meeting
    # NULL picks its own default visibly. Typed columns rather than a
    # `planning_preferences jsonb`, because a CHECK cannot guard a key inside
    # JSON and a controlled value needs guarding (ADR-019).
    preferred_session_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    topic_sequencing: Mapped[str | None] = mapped_column(String(32), nullable=True)

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
        # `IS NULL OR` is written out rather than left to three-valued CHECK
        # semantics. A CHECK does pass on NULL of its own accord, but a reader
        # should not have to remember that to see that an unset preference is
        # allowed.
        CheckConstraint(
            "preferred_session_minutes IS NULL OR (preferred_session_minutes >= "
            f"{MINIMUM_SESSION_MINUTES} AND preferred_session_minutes <= "
            f"{MAXIMUM_SESSION_MINUTES})",
            name="preferred_session_minutes_within_bounds",
        ),
        CheckConstraint(
            "topic_sequencing IS NULL OR "
            + in_clause("topic_sequencing", TOPIC_SEQUENCING_CHOICES),
            name="topic_sequencing_is_known",
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


class StudyPlan(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """One generated plan of recommended work toward a study goal.

    A plan is a snapshot. `generation_reason` records why it was written, in the
    terms that produced it, and is never rewritten afterwards -- so a plan set
    aside months ago still explains itself, which is what makes a plan history
    worth keeping.

    `learner_id` sits beside `study_goal_id` although the goal already names the
    learner. docs/database/schema.md carries both, and the required index leads on
    `learner_id`, so a learner's plans are reachable without joining through their
    goals.

    `period_start` and `period_end` are nullable as that document has them. A
    roadmap's end is the goal's horizon, which is absent only when the goal aims
    at an examination schedule publishing no sitting day and carries no target
    date beside it -- a shape the seed refuses to create but a database can hold.
    """

    __tablename__ = "study_plans"

    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    study_goal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_goals.id"), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(32), nullable=False)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    generation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(in_clause("plan_type", PLAN_TYPES), name="plan_type_is_known"),
        CheckConstraint(in_clause("status", PLAN_STATUSES), name="status_is_known"),
        # The access pattern docs/database/schema.md lists for this table: a
        # learner's plans for one goal, in a given state, by the period they
        # cover. It also serves the read generation makes before it writes --
        # every active plan of the goal being replanned.
        Index(
            "ix_study_plans_learner_id_study_goal_id_status_period_start",
            "learner_id",
            "study_goal_id",
            "status",
            "period_start",
        ),
    )


class PlanItem(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """One recommended action inside a study plan.

    `topic_id` is nullable, as docs/database/schema.md has it, so a later item
    recommending work that belongs to no single topic has somewhere to live.
    Nothing writes one today: every item this planner produces names a topic.

    `scheduled_for` is null on a roadmap item and set on a weekly one. A roadmap
    says what order to work in; only a dated plan says which day.

    `status` records whether planned work happened, and is deliberately separate
    from the learner's long-term topic progress: completing a plan item is not a
    claim about understanding, which is rule 4 of the domain model.
    """

    __tablename__ = "plan_items"

    study_plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_plans.id"), nullable=False)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduled_for: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    recommendation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(in_clause("action_type", PLAN_ITEM_ACTIONS), name="action_type_is_known"),
        CheckConstraint(in_clause("status", PLAN_ITEM_STATUSES), name="status_is_known"),
        # docs/database/schema.md approves this bound. An item estimated at zero
        # minutes is scheduling overhead rather than study, and a negative one is
        # always a mistake.
        CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes > 0",
            name="estimated_minutes_is_positive",
        ),
        # The access pattern docs/database/schema.md lists: one plan's items, by
        # the day they fall on and what has become of them.
        Index(
            "ix_plan_items_study_plan_id_scheduled_for_status",
            "study_plan_id",
            "scheduled_for",
            "status",
        ),
    )
