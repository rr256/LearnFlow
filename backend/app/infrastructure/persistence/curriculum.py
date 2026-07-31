"""Persistence models for the curriculum hierarchy.

Implements the *Curriculum* schema area of docs/database/schema.md:

    learning_programs -> curriculum_versions -> subjects -> topics

plus the ``topic_relationships`` edge table. The remaining schema areas --
learner planning, progress, resources, and assessment -- arrive with the
milestones that use them.

Controlled values are stored as text guarded by a CHECK constraint rather than a
PostgreSQL enum, one of the two forms schema.md permits. Adding a value then
stays an ordinary constraint change instead of an `ALTER TYPE`, and the value a
learner sees remains readable in the database. The domain layer holds the
authoritative vocabulary once these concepts have domain types; the constraints
below mirror it, they do not define it.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import (
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UuidPrimaryKeyMixin,
)

CURRICULUM_VERSION_STATUSES = ("draft", "active", "retired")
TOPIC_RELATIONSHIP_TYPES = ("prerequisite", "recommended_before", "related")


def _in_clause(column: str, allowed: tuple[str, ...]) -> str:
    """Render a SQL membership test for a controlled text column."""
    values = ", ".join(f"'{value}'" for value in allowed)
    return f"{column} IN ({values})"


class LearningProgram(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """A reusable learning journey such as GATE CSE."""

    __tablename__ = "learning_programs"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class CurriculumVersion(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """A versioned curriculum belonging to one learning program."""

    __tablename__ = "curriculum_versions"

    learning_program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_programs.id"), nullable=False
    )
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The type is stated rather than inferred: a bare `Mapped[datetime]` maps to
    # a naive DateTime, which schema.md forbids for every timestamp.
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("learning_program_id", "version_label"),
        CheckConstraint(
            _in_clause("status", CURRICULUM_VERSION_STATUSES),
            name="status_is_known",
        ),
        # "At most one active version per program" is enforced as a partial
        # unique index rather than left to application workflow, which is the
        # stricter of the two options schema.md allows. A second active version
        # would make "the current curriculum" ambiguous for every learner
        # planning against it, so the database refuses it outright.
        Index(
            "uq_curriculum_versions_active_learning_program_id",
            "learning_program_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )


class Subject(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """A major curriculum area within a curriculum version."""

    __tablename__ = "subjects"

    curriculum_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_versions.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("curriculum_version_id", "code"),
        UniqueConstraint("curriculum_version_id", "position"),
    )


class Topic(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """A teachable, trackable unit within a subject, optionally nested."""

    __tablename__ = "topics"

    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    parent_topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id"), nullable=True
    )
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # NOT NULL with no server default: the seed or use case creating a topic
    # states whether progress can be recorded against it. The Python-side
    # default keeps the common case convenient without letting raw SQL omit it.
    is_trackable: Mapped[bool] = mapped_column(nullable=False, default=True)

    __table_args__ = (
        # NULLS NOT DISTINCT (PostgreSQL 15+) so the rule also covers root
        # topics. Under the default NULLS DISTINCT, every root topic has a NULL
        # parent and PostgreSQL treats each NULL as unique, which would let a
        # subject hold two root topics of the same name -- the exact collision
        # this constraint exists to prevent.
        UniqueConstraint(
            "subject_id",
            "parent_topic_id",
            "name",
            postgresql_nulls_not_distinct=True,
        ),
        # A topic code is unique within its subject at every depth, not merely
        # among siblings, so a code identifies one topic no matter where it sits
        # in the tree. That is what lets the seed match on a code and rename the
        # topic underneath it.
        #
        # This one keeps the DEFAULT null behaviour, deliberately opposite to the
        # constraint above: `code` is optional, so an unnumbered curriculum
        # leaves every code NULL. Under NULLS NOT DISTINCT a subject could hold
        # only one such topic. Here each NULL stays distinct and only real
        # duplicate codes are rejected.
        UniqueConstraint("subject_id", "code"),
        # Reading a subject's topics in display order is the curriculum API's
        # primary access pattern; listed under Required Indexes in schema.md.
        Index(None, "subject_id", "parent_topic_id", "position"),
    )


class TopicRelationship(CreatedAtMixin, Base):
    """A prerequisite or sequencing edge between two topics.

    Write-once reference data, so it carries ``created_at`` only: changing the
    relationship type means a different edge, which is a delete and an insert.
    """

    __tablename__ = "topic_relationships"

    source_topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"), primary_key=True)
    target_topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"), primary_key=True)
    relationship_type: Mapped[str] = mapped_column(String(32), primary_key=True)

    __table_args__ = (
        CheckConstraint(
            _in_clause("relationship_type", TOPIC_RELATIONSHIP_TYPES),
            name="relationship_type_is_known",
        ),
        CheckConstraint(
            "source_topic_id <> target_topic_id",
            name="source_and_target_differ",
        ),
    )
