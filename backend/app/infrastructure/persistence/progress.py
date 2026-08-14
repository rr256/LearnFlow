"""Persistence models for what a learner has recorded, and what is due again.

Implements the *Progress and revision* schema area of docs/database/schema.md
except for ``study_activities``:

    learners + topics -> learner_topic_progress
                      -> revision_records

The area is created **partially**, per ADR-011 and ADR-017. Three columns
docs/database/schema.md holds as an approved target are deliberately absent:

- ``material_status`` and ``material_completed_at`` belong to material
  completion, which nothing records yet.
- ``last_studied_at`` can only be filled from a study activity, and
  ``study_activities`` does not exist.

Creating a column before the code that maintains it fixes a shape no requirement
has yet constrained, which is the trap ADR-011 exists to avoid. Each arrives with
the change that writes it.

``stage_source`` is present from the start, though every row written today says
``learner``. It is what distinguishes a stage the learner chose from one later
derived from quiz or external-test evidence, and FR-005 requires the product not
to claim mastery from a single signal. Adding it later would mean a migration
over rows whose origin is no longer recoverable.

A topic with no row here has no recorded stage, which reads as *Not explored* --
the neutral starting state. The row is created by the learner's own action, so no
page load leaves 65 records behind.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
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

LEARNING_STAGES = (
    "not_explored",
    "building_foundation",
    "developing_confidence",
    "practice_ready",
    "strong_understanding",
)
"""The five learner-visible stages, in the stored `snake_case` form.

docs/domain/terminology.md holds the display labels these render as. The order is
the progression a learner moves along, not a score: a stage guides the next
action and is never a permanent claim of mastery.
"""

STAGE_SOURCES = ("learner", "derived", "mixed")


class LearnerTopicProgress(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """One learner's recorded state for one topic."""

    __tablename__ = "learner_topic_progress"

    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"), nullable=False)
    learning_stage: Mapped[str] = mapped_column(String(32), nullable=False)
    # Whether the learner set this stage themselves or evidence produced it. No
    # database default: the writer states which, because a row that cannot say
    # where its stage came from is one a later derived writer may overwrite
    # without knowing it is discarding a learner's own answer.
    stage_source: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        # One record per learner and topic, which is what makes the update path
        # an upsert rather than an append. Listed under Required Indexes in
        # schema.md as a unique index; a unique constraint creates one.
        UniqueConstraint("learner_id", "topic_id"),
        CheckConstraint(
            in_clause("learning_stage", LEARNING_STAGES),
            name="learning_stage_is_known",
        ),
        CheckConstraint(
            in_clause("stage_source", STAGE_SOURCES),
            name="stage_source_is_known",
        ),
    )


REVISION_STATUSES = ("due", "scheduled", "completed", "skipped", "postponed")
"""The statuses `revision_records.status` accepts.

Every revision is written `due`. **REV-003 moves one to `completed`, `skipped`,
or `postponed`, and back again**: all four are things a learner says about their
own review, and each is reversible. That is PLN-004's shape for a plan item, and
a learner meeting both should not have to learn two sets of rules.

`scheduled` is approved and **unwritten**, as `scheduled_for` below is. Naming a
day for a revision is a second capability -- it raises what happens when that day
passes, and whether the schedule or the learner owns the date -- and inventing it
alongside the first would be two features in one change. The constraint carries
it so that arrives as a use-case change rather than a migration, which is the
argument ADR-020 made for `plan_items.status` and which paid off three times.
"""

REVISION_TRIGGERS = ("completed_plan_item", "completed_revision")
"""Why a revision was created.

`completed_plan_item` is a topic the learner finished planned work on;
`completed_revision` is the same topic coming back after a review they completed,
which is the *prior revision history* FR-006's fourth criterion names.

docs/database/schema.md describes the column as holding "why revision was
created, e.g. completion, low evidence, spaced schedule". Low evidence needs quiz
and external-test records, which do not exist, so only the two triggers something
actually writes are permitted here. A third arrives with the evidence that
justifies it.
"""

SETTLED_REVISION_STATUSES = frozenset({"completed", "skipped", "postponed"})
"""The statuses in which a revision is not offered as due again.

The mirror of `SETTLED_STATUSES` for a plan item, and it means the same thing:
something has already been said about this, so nothing should put it back in
front of the learner on its own. `due` and `scheduled` are outside it.
"""


class RevisionRecord(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """One topic coming back for review, and what became of it.

    Created by the learner asking for revisions to be scheduled -- never as a
    side effect of completing a plan item, which would move a record they did not
    name and breach ADR-021's "only the named item moves".

    ``plan_item_id`` records the completed work this revision came from, and is
    nullable because a revision triggered by an earlier *revision* has no plan
    item behind it. It is deliberately **not** a cascade: a plan item lives on a
    plan that adaptation supersedes, and a revision must outlive that.

    ``status`` records whether the review happened. Like a plan item's, it is
    separate from the learner's long-term topic progress: completing a revision
    is not a claim about understanding, which is rule 4 of the domain model, and
    nothing here writes a learning stage.

    ``scheduled_for`` is created and never written, for the reason
    `REVISION_STATUSES` gives about `scheduled`.
    """

    __tablename__ = "revision_records"

    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"), nullable=False)
    plan_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plan_items.id"), nullable=True
    )
    due_on: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_for: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    recommendation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(in_clause("status", REVISION_STATUSES), name="status_is_known"),
        CheckConstraint(in_clause("trigger_type", REVISION_TRIGGERS), name="trigger_type_is_known"),
        # The access pattern docs/database/schema.md lists under Required
        # Indexes: one learner's revisions, by the day they fall due and what has
        # become of them.
        Index("ix_revision_records_learner_id_due_on_status", "learner_id", "due_on", "status"),
    )
