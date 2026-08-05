"""Persistence model for what a learner has recorded about one topic.

Implements the first table of the *Progress and revision* schema area of
docs/database/schema.md:

    learners + topics -> learner_topic_progress

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

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
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
