"""add resource note search index

Adds one GIN index over the text of ``resource_notes``, so RES-013 can find the
passages of a learner's own notes that mention a topic they chose. It arrives
with the code that reads it, which is the ordering ADR-011 prescribes.

**Additive, and it touches no data.** One ``CREATE INDEX``; **no table is
created, altered, or dropped, no column is added, and no row is read, rewritten,
or reinterpreted**. An index is derived structure: it stores no learner text that
was not already in the table, and dropping it in the downgrade loses nothing a
learner wrote.

This is deliberately **an index and not a column**. A stored ``tsvector``
generated column would have been marginally faster and would have meant altering
an existing learner-owned table to hold a **derived representation of note
text** — exactly what ADR-037 kept out of the schema. An expression index keeps
the derived form as something PostgreSQL maintains for itself, invisible to every
query that does not ask for it. See ADR-038.

The indexed expression must match the one the repository searches with, **exactly
and including the configuration name**, or the index is silently unused. It is
written out in full here rather than imported, because a migration describes the
schema at one moment in history and must keep applying after the application
constant it mirrors has moved on.

Two details the expression depends on:

- **The two-argument ``to_tsvector`` with a literal configuration is required.**
  The one-argument form reads ``default_text_search_config`` at runtime, which
  makes it ``STABLE`` rather than ``IMMUTABLE``, and PostgreSQL refuses to build
  an index on a non-immutable expression.
- **``title`` and ``body`` are both ``NOT NULL``**, so concatenating them needs no
  ``coalesce``; a null in either would otherwise make the whole document null.

No extension is installed. ``english`` is a built-in text-search configuration,
so this needs neither ``pg_trgm`` nor ``unaccent`` and adds no dependency.

Revision ID: 20260820_01
Revises: 20260819_01
Created: 2026-08-19

"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260820_01"
down_revision: str | None = "20260819_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_resource_notes_search"

SEARCH_DOCUMENT = "to_tsvector('english', title || ' ' || body)"
"""The indexed expression, mirroring `_searchable_document` in the repository."""


def upgrade() -> None:
    """Create the full-text index over each note's title and body."""
    op.execute(f"CREATE INDEX {INDEX_NAME} ON resource_notes USING gin ({SEARCH_DOCUMENT})")


def downgrade() -> None:
    """Drop the index.

    **This loses nothing a learner wrote.** An index is derived structure over
    text that stays in the table, unlike revision `20260819_01`, whose downgrade
    discards the notes themselves. Searching simply falls back to a sequential
    scan.
    """
    op.execute(f"DROP INDEX {INDEX_NAME}")
