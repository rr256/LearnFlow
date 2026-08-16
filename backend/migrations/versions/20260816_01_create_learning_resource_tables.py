"""create learning resource tables

Adds ``resources`` and ``resource_topic_links`` to the *Resources and RAG
metadata* schema area of docs/database/schema.md, which had no table until now.
They arrive with the catalogue code that reads them (RES-001 to RES-004), which
is the ordering ADR-011 prescribes: this migration and that use case travel
together.

**Additive.** Two CREATE TABLEs and two indexes; no existing table is altered and
no stored row is read, rewritten, or reinterpreted. A learner with goals, plans,
items, completions, progress, and revisions keeps every one of them untouched,
and both new tables start empty because a resource is created only when the
learner registers one.

Four departures from the approved tables, all recorded by ADR-032:

- ``storage_key`` and ``metadata`` are **not created**. Both describe a stored
  file and nothing uploads one; this catalogue records where material is, not
  the material. They arrive with the ingestion change, as
  ``learner_topic_progress`` left three columns to the code that would maintain
  them.
- The approved constraint *at least one of ``storage_key`` or
  ``external_reference``* is expressed over the two columns that do exist:
  ``source_label`` or ``external_reference``. The invariant is the same one — a
  resource must say where its material is — read for a catalogue that stores no
  files.
- ``resource_type`` permits five of its seven documented values, and ``status``
  two of its five. ``image`` and ``attachment`` name uploaded files; ``processing``,
  ``ready``, and ``failed`` are ingestion states, and ``resource_ingestions``
  does not exist, so a resource could enter one and never leave it.
  ``relationship_type`` by contrast carries **all four** of its values although
  only ``primary`` is written: choosing between them needs no storage that is
  missing, so offering them later is a use-case change rather than a migration —
  the argument ADR-020 made for ``plan_items.status``.
- Controlled columns are ``varchar(32)`` guarded by a CHECK rather than the bare
  ``text`` docs/database/schema.md describes, following its own *Conventions*,
  ADR-011's validated-text rule, and the precedent ``day_of_week``,
  ``topic_sequencing``, the study-plan columns, and the revision columns each
  set.

``resource_ingestions`` is deliberately not created. It arrives with the
extractor and the vector index that give it something to track.

The two indexes are the ones docs/database/schema.md lists under *Required
Indexes* for these tables.

Constraint names follow the convention on ``Base.metadata``. Primary, unique, and
foreign-key conventions ignore a supplied name, so those are written out in full;
the check convention interpolates the supplied name, so a check passes only its
distinguishing suffix.

Revision ID: 20260816_01
Revises: 20260813_01
Created: 2026-08-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_01"
down_revision: str | None = "20260813_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESOURCE_TYPES = ("pdf", "note", "pyq", "formula_sheet", "video_reference")
RESOURCE_STATUSES = ("registered", "archived")
RESOURCE_TOPIC_ROLES = ("primary", "supporting", "practice", "revision")


def _in_clause(column: str, allowed: tuple[str, ...]) -> str:
    """Render the membership test the model builds for the same column.

    Written out here rather than imported: a migration describes the schema at
    one moment in history and must keep applying after the application constant
    it mirrors has moved on.
    """
    values = ", ".join(f"'{value}'" for value in allowed)
    return f"{column} IN ({values})"


def upgrade() -> None:
    """Create ``resources``, ``resource_topic_links``, and their indexes."""
    op.create_table(
        "resources",
        sa.Column("id", sa.Uuid(), nullable=False),
        # Nullable, as docs/database/schema.md approves, so curated or shared
        # content has somewhere to live later. Nothing writes an ownerless row
        # today: the use case requires an owner on every write.
        sa.Column("owner_learner_id", sa.Uuid(), nullable=True),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_label", sa.Text(), nullable=True),
        sa.Column("external_reference", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_resources"),
        sa.ForeignKeyConstraint(
            ["owner_learner_id"],
            ["learners.id"],
            name="fk_resources_owner_learner_id_learners",
        ),
        sa.CheckConstraint(
            _in_clause("resource_type", RESOURCE_TYPES), name="resource_type_is_known"
        ),
        sa.CheckConstraint(_in_clause("status", RESOURCE_STATUSES), name="status_is_known"),
        sa.CheckConstraint(
            "source_label IS NOT NULL OR external_reference IS NOT NULL",
            name="names_a_location",
        ),
    )
    op.create_index(
        "ix_resources_owner_learner_id_status",
        "resources",
        ["owner_learner_id", "status"],
    )

    op.create_table(
        "resource_topic_links",
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "resource_id", "topic_id", "relationship_type", name="pk_resource_topic_links"
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["resources.id"],
            name="fk_resource_topic_links_resource_id_resources",
        ),
        # Not a cascade. Curriculum rows are reference data that learner records
        # reference, and docs/database/schema.md forbids deleting one casually.
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name="fk_resource_topic_links_topic_id_topics",
        ),
        sa.CheckConstraint(
            _in_clause("relationship_type", RESOURCE_TOPIC_ROLES),
            name="relationship_type_is_known",
        ),
    )
    op.create_index(
        "ix_resource_topic_links_topic_id_resource_id",
        "resource_topic_links",
        ["topic_id", "resource_id"],
    )


def downgrade() -> None:
    """Drop both tables, and their indexes with them.

    The links go first: they reference ``resources``, so dropping the parent
    first would fail. Each index is dropped explicitly before its table for
    symmetry with the upgrade. No constraint is named: dropping a table takes its
    checks with it, which also keeps this clear of the ``ck`` naming convention
    that bit revision ``20260806_02``. See docs/database/migrations.md.
    """
    op.drop_index("ix_resource_topic_links_topic_id_resource_id", table_name="resource_topic_links")
    op.drop_table("resource_topic_links")
    op.drop_index("ix_resources_owner_learner_id_status", table_name="resources")
    op.drop_table("resources")
