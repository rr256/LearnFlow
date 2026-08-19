"""create resource notes table

Adds ``resource_notes`` to the *Resources and RAG metadata* schema area of
docs/database/schema.md, which had ``resources`` and ``resource_topic_links``
until now. It arrives with the code that reads it (RES-009 to RES-012), which is
the ordering ADR-011 prescribes: this migration and that use case travel
together.

**This table is added beyond the tables docs/database/schema.md approves**, which
is the departure ADR-037 records and the second time this repository has gone
past that document — ``questions.author_learner_id`` was the first, added by
migration ``20260818_01`` and recorded in that area's review. The approved area
anticipated *derived* representations of learner material: chunks and embeddings
in a vector index, tracked by ``resource_ingestions``. Text the learner **typed
themselves** is neither derived nor a file, so no approved table could hold it.

**Additive.** One CREATE TABLE and one index; no existing table is altered and no
stored row is read, rewritten, or reinterpreted. A learner with goals, plans,
items, completions, progress, revisions, resources, questions, quizzes, and
attempts keeps every one of them untouched, and the new table starts empty
because a note exists only when the learner writes one.

Three points worth recording about the shape:

- ``body`` is ``text`` and unbounded in the column, as docs/database/schema.md
  requires of learner-facing prose. **How much a learner may actually write is an
  application rule** (``MAX_NOTE_BODY_LENGTH``, 20,000 characters), so raising it
  later is a use-case change rather than a migration — the argument ADR-020 made
  for ``plan_items.status``. What the table enforces is only that a note is not
  empty.
- ``status`` is ``varchar(32)`` guarded by a CHECK rather than a bare ``text``,
  following docs/database/schema.md's own *Conventions*, ADR-011's validated-text
  rule, and the precedent ``day_of_week``, ``topic_sequencing``, the study-plan
  columns, the revision columns, and the resource columns each set. Both its
  values are written: unlike ``resources.status``, no state here waits on storage
  that does not exist.
- **There is no topic link table.** A note belongs to one resource and inherits
  the topics that resource covers, so a learner correcting what a resource covers
  moves its notes with it and cannot leave the two disagreeing.

``resource_ingestions`` is still deliberately not created, and
``resources.storage_key`` and ``resources.metadata`` are still deliberately
absent. Nothing uploads, downloads, extracts, chunks, embeds, or indexes
anything; a note is text a learner typed, and this migration gives it somewhere
to live and nothing more.

The foreign key is **not** a cascade. Nothing in LearnFlow deletes a resource — a
learner puts one aside with ``status: archived``, reversibly — so a cascade would
describe a deletion path that does not exist, which is the reasoning migration
``20260816_01`` applied to ``resource_topic_links``.

Constraint names follow the convention on ``Base.metadata``. Primary, unique, and
foreign-key conventions ignore a supplied name, so those are written out in full;
the check convention interpolates the supplied name, so a check passes only its
distinguishing suffix.

Revision ID: 20260819_01
Revises: 20260818_01
Created: 2026-08-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_01"
down_revision: str | None = "20260818_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESOURCE_NOTE_STATUSES = ("active", "archived")


def _in_clause(column: str, allowed: tuple[str, ...]) -> str:
    """Render the membership test the model builds for the same column.

    Written out here rather than imported: a migration describes the schema at
    one moment in history and must keep applying after the application constant
    it mirrors has moved on.
    """
    values = ", ".join(f"'{value}'" for value in allowed)
    return f"{column} IN ({values})"


def upgrade() -> None:
    """Create ``resource_notes`` and its index."""
    op.create_table(
        "resource_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        # The learner's own text, stored exactly as they wrote it. Unbounded in
        # the column; the length they may write is an application rule.
        sa.Column("body", sa.Text(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_resource_notes"),
        # Not a cascade: nothing deletes a resource, so a cascade would describe
        # a path that does not exist. See the module docstring.
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["resources.id"],
            name="fk_resource_notes_resource_id_resources",
        ),
        sa.CheckConstraint(_in_clause("status", RESOURCE_NOTE_STATUSES), name="status_is_known"),
        # A note with no text in it is a title and nothing else. The application
        # refuses one first; this is what makes the rule true of the table.
        #
        # A regex rather than `length(btrim(body)) > 0`: PostgreSQL's one-argument
        # `btrim` strips spaces alone, so a body of newlines and tabs would pass
        # it. This asks the question actually being asked -- is there a character
        # here that is not whitespace?
        sa.CheckConstraint("body ~ '[^[:space:]]'", name="body_is_not_empty"),
    )
    # One resource's notes, and whether they are put aside: the access pattern
    # every read uses, mirroring `resources(owner_learner_id, status)` one level
    # down.
    op.create_index(
        "ix_resource_notes_resource_id_status",
        "resource_notes",
        ["resource_id", "status"],
    )


def downgrade() -> None:
    """Drop the table, and its index with it.

    The index is dropped explicitly before the table for symmetry with the
    upgrade. No constraint is named: dropping a table takes its checks with it,
    which also keeps this clear of the ``ck`` naming convention that bit revision
    ``20260806_02``. See docs/database/migrations.md.

    **This discards learner-written text**, which no earlier downgrade in this
    repository does — every table dropped so far held records a learner could
    recreate by asking again. A downgrade past this revision loses notes that
    exist nowhere else, so it is a deliberate act on a database whose contents
    are expendable, exactly as docs/database/migrations.md requires of every
    downgrade.
    """
    op.drop_index("ix_resource_notes_resource_id_status", table_name="resource_notes")
    op.drop_table("resource_notes")
