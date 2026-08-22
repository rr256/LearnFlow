"""The SQLAlchemy adapter behind `ResourceFileRepository`.

It stores **rows about files, never file bytes**. The bytes live in a local
volume behind `ResourceFileStorage`; this table holds what a learner called the
file, how big it is, how many pages it has, and the opaque key that finds it.

**Ownership is not stored here.** A file hangs off a resource, and the resource
carries the owner, so the use case checks ownership there. Duplicating it on this
table would create two places for it to disagree.

**Removal deletes the row and nothing else.** The bytes are the storage
adapter's, unlinked by the use case in the same request once this row is marked
deleted — and before the commit, which is why a failed unlink takes this row's
deletion down with it.
"""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.application.dto.resource_file import ResourceFileFilters, ResourceFileRecord
from app.infrastructure.persistence.resources import ResourceFile


class SqlAlchemyResourceFileRepository:
    """Reads and writes `resource_files` through one session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one unit of work."""
        self._session = session

    def count_files(self, resource_id: uuid.UUID) -> int:
        """How many files this resource holds, in **any** status.

        Archived files count: they still occupy the volume, so they still count
        against the ceiling. The figure enforces a bound and is never reported.
        """
        statement = select(ResourceFile.id).where(ResourceFile.resource_id == resource_id)
        return len(self._session.execute(statement).scalars().all())

    def list_files(
        self, *, resource_id: uuid.UUID, filters: ResourceFileFilters
    ) -> tuple[ResourceFileRecord, ...]:
        """This resource's files, newest first.

        An empty `statuses` means every status, the shape the note and resource
        filters already use.
        """
        statement = select(ResourceFile).where(ResourceFile.resource_id == resource_id)
        if filters.statuses:
            statement = statement.where(ResourceFile.status.in_(filters.statuses))
        statement = statement.order_by(ResourceFile.created_at.desc(), ResourceFile.id.desc())
        rows = self._session.execute(statement).scalars().all()
        return tuple(_record(row) for row in rows)

    def find_file(self, file_id: uuid.UUID) -> ResourceFileRecord | None:
        """One file by identifier, whatever its status."""
        row = self._session.get(ResourceFile, file_id)
        return None if row is None else _record(row)

    def add_file(self, record: ResourceFileRecord) -> None:
        """Record a stored file."""
        self._session.add(
            ResourceFile(
                id=record.id,
                resource_id=record.resource_id,
                storage_key=record.storage_key,
                original_filename=record.original_filename,
                byte_size=record.byte_size,
                page_count=record.page_count,
                content_type=record.content_type,
                checksum=record.checksum,
                status=record.status,
            )
        )

    def update_file(self, record: ResourceFileRecord) -> None:
        """Save a changed status.

        **Only the status moves.** The storage key, the filename, the size, the
        page count, and the checksum all describe bytes that have not changed, so
        rewriting any of them would make the row disagree with what is on disk.
        """
        row = self._session.get(ResourceFile, record.id)
        if row is None:
            return
        row.status = record.status

    def delete_file(self, file_id: uuid.UUID) -> None:
        """Remove the row. A row that is not there is already in the wanted state."""
        row = self._session.get(ResourceFile, file_id)
        if row is not None:
            self._session.delete(row)

    def delete_files_for_resource(self, resource_id: uuid.UUID) -> int:
        """Remove every stored-file row of one resource, returning how many went.

        **Rows only.** The bytes are the storage adapter's, and the use case
        unlinks them from keys it read before this ran.
        """
        result = self._session.execute(
            delete(ResourceFile).where(ResourceFile.resource_id == resource_id)
        )
        return result.rowcount or 0


def _record(row: ResourceFile) -> ResourceFileRecord:
    """One stored file, as the application layer sees it."""
    return ResourceFileRecord(
        id=row.id,
        resource_id=row.resource_id,
        storage_key=row.storage_key,
        original_filename=row.original_filename,
        byte_size=row.byte_size,
        page_count=row.page_count,
        content_type=row.content_type,
        checksum=row.checksum,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
