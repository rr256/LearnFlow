"""create resource files table

Adds ``resource_files`` to the *Resources and RAG metadata* schema area of
docs/database/schema.md, which has held ``resources``, ``resource_topic_links``,
and ``resource_notes`` until now. It arrives with the code that reads it
(RES-014 to RES-017), which is the ordering ADR-011 prescribes: this migration
and that use case travel together.

**This table is added beyond the tables docs/database/schema.md approves**, which
is the departure ADR-040 records and the third time this repository has gone past
that document — ``questions.author_learner_id`` was the first and
``resource_notes`` the second. The approved area anticipated **one** file per
resource: ``resources.storage_key`` and ``resources.metadata`` are columns on
``resources`` itself. A learner may keep several PDFs against one piece of
material, which no 1:1 column pair can hold, so a table is created rather than
those two columns being half-built into a shape they cannot support.
``resources.storage_key`` and ``resources.metadata`` therefore stay **deliberately
absent**, as does ``resource_ingestions``: nothing extracts, chunks, embeds, or
indexes anything, and this table is not an ingestion record.

**Additive.** One CREATE TABLE and one index; no existing table is altered and no
stored row is read, rewritten, or reinterpreted. A learner with goals, plans,
items, completions, progress, revisions, resources, notes, questions, quizzes,
and attempts keeps every one of them untouched, and the new table starts empty
because a file exists only once the learner chooses one.

**No file bytes are stored here.** The bytes live in a Docker named volume
mounted only into the backend; ``storage_key`` is the opaque reference that finds
them. A ``bytea`` column was rejected deliberately: binaries bloat every dump and
every backup, and the two are better backed up by their own means. That makes
backup **two things** rather than one, which docs/deployment/docker.md records.

Four points worth recording about the shape:

- ``original_filename`` is what the learner called the file, kept only so a
  download can be offered under a name they recognise. It is **metadata, never a
  path**: what lands on disk is named from a server-generated identifier, so
  nothing a browser sends can steer where a file is written.
- ``byte_size`` is ``bigint`` rather than ``integer``. The application caps a file
  far below either limit, but a size column that could overflow is a poor place
  to be exact, and widening one later is a rewrite of every row.
- ``status`` is ``varchar(32)`` guarded by a CHECK, following the convention
  ``day_of_week``, ``topic_sequencing``, the study-plan columns, the revision
  columns, and the resource columns each set. Both values are written; the
  ingestion states ``processing``, ``ready``, and ``failed`` are absent because
  nothing would move a file out of them.
- **There is no owner column and no topic link table.** A file hangs off a
  resource, the resource carries the owner and the topics, and duplicating either
  here would create a second place for them to disagree.

The foreign key is **not** a cascade. Nothing in LearnFlow deletes a resource — a
learner puts one aside with ``status: archived``, reversibly — so a cascade would
describe a deletion path that does not exist, which is the reasoning migrations
``20260816_01`` and ``20260819_01`` each applied. Safe permanent deletion is
RES-005, still unimplemented, and it must coordinate rows and bytes together.

Constraint names follow the convention on ``Base.metadata``. Primary, unique, and
foreign-key conventions ignore a supplied name, so those are written out in full;
the check convention interpolates the supplied name, so a check passes only its
distinguishing suffix.

Revision ID: 20260821_01
Revises: 20260820_01
Created: 2026-08-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_01"
down_revision: str | None = "20260820_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESOURCE_FILE_STATUSES = ("active", "archived")


def _in_clause(column: str, allowed: tuple[str, ...]) -> str:
    """Render the membership test the model builds for the same column.

    Written out here rather than imported: a migration describes the schema at
    one moment in history and must keep applying after the application constant
    it mirrors has moved on.
    """
    values = ", ".join(f"'{value}'" for value in allowed)
    return f"{column} IN ({values})"


def upgrade() -> None:
    """Create ``resource_files`` and its index."""
    op.create_table(
        "resource_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        # Opaque, and issued by the storage adapter. Never returned by an
        # endpoint: a resource endpoint may not expose a storage location.
        sa.Column("storage_key", sa.Text(), nullable=False),
        # The learner's own name for the file. Metadata, never a path.
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        # SHA-256 of the bytes, so corruption is detectable without reading the
        # file back in full. Sixty-four hexadecimal characters.
        sa.Column("checksum", sa.String(length=64), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_resource_files"),
        # Not a cascade: nothing deletes a resource. See the module docstring.
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["resources.id"],
            name="fk_resource_files_resource_id_resources",
        ),
        sa.CheckConstraint(_in_clause("status", RESOURCE_FILE_STATUSES), name="status_is_known"),
        # A stored file with no bytes is a row describing nothing. The
        # application refuses an empty upload first; this makes it true of the
        # table.
        sa.CheckConstraint("byte_size > 0", name="has_bytes"),
        sa.CheckConstraint("page_count >= 0", name="page_count_is_not_negative"),
        # A key of whitespace would name no file. `btrim` is deliberately not
        # used: PostgreSQL's one-argument form strips spaces alone, so a key of
        # tabs would pass a check meant to refuse it.
        sa.CheckConstraint("storage_key ~ '[^[:space:]]'", name="storage_key_is_not_empty"),
    )
    # The read path is always "this resource's files", so the index matches it
    # rather than indexing the foreign key on its own.
    op.create_index(
        "ix_resource_files_resource_status",
        "resource_files",
        ["resource_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop ``resource_files`` and its index.

    **This removes the record of every stored file, and leaves the bytes in the
    volume.** Downgrading does not delete a learner's PDFs — nothing in LearnFlow
    does — but it orphans them: the volume keeps files nothing can name any more.
    Re-applying the upgrade creates an empty table, so the rows do not come back.

    That asymmetry is deliberate and is the honest one. A downgrade that deleted
    files would destroy learner material to undo a schema change, which is worse
    than leaving bytes that can be reclaimed by hand.
    """
    op.drop_index("ix_resource_files_resource_status", table_name="resource_files")
    op.drop_table("resource_files")
