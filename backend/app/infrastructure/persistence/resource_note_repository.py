"""SQLAlchemy implementation of the resource-note repository port.

Serves RES-009 to RES-012. It maps rows to the application's plain records and
back, and reads one resource's notes a page at a time.

It decides nothing. Whether a note belongs to the effective learner, whether its
material is still in the catalogue, how long a note may be, and how many one
resource may hold are all settled by the use case
(docs/architecture/dependency-rules.md).

**Nothing here deletes.** A note is put aside by moving its status, so there is
no removal statement to be reached by mistake.

**Nothing here rewrites a learner's text.** ``body`` is read and written exactly
as the use case handed it over: no normalisation, no truncation, no collapsing of
whitespace. docs/rag/ingestion.md normalises *extracted* text before chunking it,
and that is a pipeline reading files rather than this.

The session's transaction is owned by the caller. Nothing here commits.
"""

import uuid

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session

from app.application.dto.resource_note import ResourceNoteFilters, ResourceNoteRecord
from app.infrastructure.persistence.resources import ResourceNote as ResourceNoteRow


class SqlAlchemyResourceNoteRepository:
    """Reads and writes resource notes through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one unit of work."""
        self._session = session

    def count_notes(self, *, resource_id: uuid.UUID, filters: ResourceNoteFilters) -> int:
        """How many of this resource's notes match, ignoring any page window."""
        total = self._session.scalar(
            select(func.count()).select_from(ResourceNoteRow).where(*_filters(resource_id, filters))
        )
        return int(total or 0)

    def count_all_notes(self, resource_id: uuid.UUID) -> int:
        """How many notes this resource holds, whatever their status.

        Read only to decide whether one more may be written. Notes put aside are
        counted, because a bound that ignored them could be stepped around by
        archiving.
        """
        total = self._session.scalar(
            select(func.count())
            .select_from(ResourceNoteRow)
            .where(ResourceNoteRow.resource_id == resource_id)
        )
        return int(total or 0)

    def list_notes(
        self,
        *,
        resource_id: uuid.UUID,
        filters: ResourceNoteFilters,
        limit: int,
        offset: int,
    ) -> tuple[ResourceNoteRecord, ...]:
        """One page of the resource's notes, newest first."""
        rows = self._session.scalars(
            _ordered(select(ResourceNoteRow).where(*_filters(resource_id, filters)))
            .limit(limit)
            .offset(offset)
        ).all()
        return tuple(_record(row) for row in rows)

    def find_note(self, note_id: uuid.UUID) -> ResourceNoteRecord | None:
        """The note with this identifier, or None."""
        row = self._session.get(ResourceNoteRow, note_id)
        return None if row is None else _record(row)

    def add_note(self, record: ResourceNoteRecord) -> None:
        """Store a new note."""
        self._session.add(
            ResourceNoteRow(
                id=record.id,
                resource_id=record.resource_id,
                title=record.title,
                body=record.body,
                status=record.status,
            )
        )

    def update_note(self, record: ResourceNoteRecord) -> None:
        """Store a changed note.

        ``resource_id`` is deliberately not written: a note belongs to the
        material it was written against, and moving one between resources is not
        something RES-012 offers.

        Raises:
            LookupError: The note is not stored. The use case has already
                established that it is, so reaching this means the row vanished
                between the read and the write.
        """
        row = self._session.get(ResourceNoteRow, record.id)
        if row is None:
            raise LookupError(f"No note is stored with identifier {record.id}.")
        row.title = record.title
        row.body = record.body
        row.status = record.status


def _filters(
    resource_id: uuid.UUID, filters: ResourceNoteFilters
) -> tuple[ColumnElement[bool], ...]:
    """The conditions a listed note must meet.

    No status is assumed. A caller wanting only what the learner is using asks
    for `active`, and one wanting what has been put aside asks for `archived`,
    which is how RES-002, PLN-002, and REV-001 treat their own statuses.
    """
    conditions: list[ColumnElement[bool]] = [ResourceNoteRow.resource_id == resource_id]
    if filters.status is not None:
        conditions.append(ResourceNoteRow.status == filters.status)
    return tuple(conditions)


def _ordered(statement: Select[tuple[ResourceNoteRow]]) -> Select[tuple[ResourceNoteRow]]:
    """Newest first, then by identifier.

    The order every learner-owned collection uses. The identifier breaks a tie
    two notes written in the same instant would otherwise leave to the database,
    which would let one page repeat or omit a record.
    """
    return statement.order_by(ResourceNoteRow.created_at.desc(), ResourceNoteRow.id)


def _record(row: ResourceNoteRow) -> ResourceNoteRecord:
    """Map a stored row onto the application's plain record."""
    return ResourceNoteRecord(
        id=row.id,
        resource_id=row.resource_id,
        title=row.title,
        body=row.body,
        status=row.status,
    )
