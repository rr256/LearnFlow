"""Persistence models for a learner's study material and what it covers.

Implements the *Resources and RAG metadata* schema area of
docs/database/schema.md, except for ``resource_ingestions``:

    resources <-> resource_topic_links -> topics

The area is created **partially**, per ADR-011. What is absent is absent because
nothing maintains it:

- ``storage_key`` and ``metadata`` describe a stored file, and nothing uploads
  one. This catalogue records **where material is**, not the material.
- ``resource_ingestions`` tracks extraction and indexing, which do not exist.

Creating a column before the code that maintains it fixes a shape no requirement
has yet constrained, which is the trap ADR-011 exists to avoid and the reason
``learner_topic_progress`` was created without three of its documented columns.
Each arrives with the change that writes it.

``owner_learner_id`` is nullable, as docs/database/schema.md approves, so curated
or shared content has somewhere to live later. **Nothing writes an ownerless
resource today**: the use case requires an owner on every write, because a row
belonging to nobody would be invisible to every learner-scoped read.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import (
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UuidPrimaryKeyMixin,
    in_clause,
)

RESOURCE_TYPES = ("pdf", "note", "pyq", "formula_sheet", "video_reference")
"""The kinds of study material this catalogue holds.

Five of the seven docs/database/schema.md documents. ``image`` and ``attachment``
each name an uploaded file, and nothing uploads one, so both arrive with the
storage change that gives a file somewhere to live.
"""

RESOURCE_STATUSES = ("registered", "archived")
"""The statuses ``resources.status`` accepts.

Two of the five docs/database/schema.md documents. ``processing``, ``ready``, and
``failed`` are ingestion lifecycle states and ``resource_ingestions`` does not
exist, so a resource could enter one and never leave it. They arrive with the
ingestion change, which needs a migration for its own table regardless -- unlike
``resource_topic_links.relationship_type`` below, whose unwritten values need no
storage that is missing and so are carried here.

``archived`` is the learner putting material aside, and it is **reversible**:
nothing in LearnFlow deletes a resource.
"""

RESOURCE_TOPIC_ROLES = ("primary", "supporting", "practice", "revision")
"""What a resource is to the topic it is linked to.

All four docs/database/schema.md documents, though **only ``primary`` is
written**: a learner links material to a topic and is not asked to grade how
central it is. Carrying the other three means offering them later is a use-case
change rather than a migration, which is the argument ADR-020 made for
``plan_items.status``.
"""


class Resource(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """One piece of study material a learner has catalogued.

    Metadata, never the material itself. ``external_reference`` holds an ``http``
    or ``https`` address; the application refuses any other scheme, so no
    absolute path on the learner's own machine is stored here or returned by any
    endpoint -- the rule docs/api/endpoints.md states for every resource
    endpoint. Material that is not on the web is described by ``source_label``,
    in the learner's own words.
    """

    __tablename__ = "resources"

    owner_learner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learners.id"), nullable=True
    )
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        CheckConstraint(in_clause("resource_type", RESOURCE_TYPES), name="resource_type_is_known"),
        CheckConstraint(in_clause("status", RESOURCE_STATUSES), name="status_is_known"),
        # docs/database/schema.md requires at least one of `storage_key` or
        # `external_reference`, so that a resource always says where its material
        # is. `storage_key` is not created, so the same invariant is expressed
        # over the two columns this catalogue does have: a record with neither a
        # link nor a label is a title and nothing else.
        CheckConstraint(
            "source_label IS NOT NULL OR external_reference IS NOT NULL",
            name="names_a_location",
        ),
        # The access pattern docs/database/schema.md lists under Required
        # Indexes: one learner's resources, and whether they are put aside.
        Index("ix_resources_owner_learner_id_status", "owner_learner_id", "status"),
    )


class ResourceTopicLink(CreatedAtMixin, Base):
    """A link between one resource and one curriculum topic.

    Write-once, so it carries ``created_at`` only, as ``topic_relationships``
    does: changing the role means a different link, which is a delete and an
    insert. A learner editing what a resource covers replaces the whole set.

    A link may name **any** stored topic, including one that only groups
    subtopics. That is deliberately unlike ``learner_topic_progress``, which the
    application restricts to a trackable topic: a stage claims something about
    understanding a unit of work, while a textbook may genuinely cover a heading.
    """

    __tablename__ = "resource_topic_links"

    resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"), primary_key=True)
    relationship_type: Mapped[str] = mapped_column(String(32), primary_key=True)

    __table_args__ = (
        CheckConstraint(
            in_clause("relationship_type", RESOURCE_TOPIC_ROLES),
            name="relationship_type_is_known",
        ),
        # The access pattern docs/database/schema.md lists under Required
        # Indexes: which resources cover a topic, which is how the curriculum and
        # revision screens read this table.
        Index("ix_resource_topic_links_topic_id_resource_id", "topic_id", "resource_id"),
    )
