"""The ports a stored PDF is reached through.

Two, kept apart on purpose. `ResourceFileStorage` holds **bytes**;
`ResourceFileRepository` holds **rows**. A database is a poor home for binaries —
a `bytea` lands in every dump and every backup — and a filesystem is a poor home
for anything you need to query. Splitting them here is what lets each live where
it belongs, and it is why the composition root binds two different adapters.

**No path crosses either boundary.** The storage port speaks in opaque
`storage_key` strings it issued itself. Application code never learns a directory,
a mount point, or a filename on disk, and therefore cannot leak one into a
response — the endpoint rule that no resource endpoint returns an absolute local
filesystem path is kept by construction rather than by filtering.

**Nothing here extracts, converts, or renders.** The storage port writes bytes,
reads them back, and nothing else: no text extraction, no OCR, no thumbnail, no
preview, and no scanning. `DocumentInspector` reads a document's **structure** —
how many pages, and whether it is encrypted — and returns no content at all.

**Nothing here deletes.** There is deliberately no removal method on either port:
a learner sets a file aside reversibly, and safe permanent deletion is a separate
feature (RES-005) that must coordinate bytes and rows together
([ADR-040](../../../../docs/adr/ADR-040-learner-uploaded-resource-files.md)).
"""

import uuid
from typing import Protocol

from app.application.dto.resource_file import (
    PdfFacts,
    ResourceFileFilters,
    ResourceFileRecord,
)


class ResourceFileStorage(Protocol):
    """Keeps the bytes of a stored file, addressed by an opaque key."""

    def store(self, *, content: bytes) -> str:
        """Write these bytes and return the key that finds them again.

        **The key is the adapter's to invent**, and callers must treat it as
        opaque. It is deliberately not derived from the learner's filename: a
        name supplied by a browser is untrusted input, and building a path out of
        one invites traversal, collision, and reserved-name problems for no
        benefit.

        Returns:
            An opaque key. Never a path, and never anything a caller may parse.
        """
        ...

    def read(self, storage_key: str) -> bytes | None:
        """The bytes behind a key, or `None` when nothing is stored there.

        A missing file is `None` rather than an exception because it is a state a
        caller must handle: a volume can be restored from a backup that predates
        a row, and the endpoint should say so plainly rather than fail.
        """
        ...


class DocumentInspector(Protocol):
    """Reads a document's structure, and never its content."""

    def inspect_pdf(self, content: bytes) -> PdfFacts | None:
        """What this PDF is, structurally, or `None` when it cannot be read.

        Returns page count and whether the document is encrypted. **It returns no
        text**, by design: this feature stores files and does not extract from
        them, and a method that could return content would be the place that
        quietly started to.

        `None` means unreadable — malformed, truncated, or not a PDF at all — and
        the caller refuses the upload rather than storing something LearnFlow
        cannot open.
        """
        ...


class ResourceFileRepository(Protocol):
    """Reads and writes the rows describing a resource's files."""

    def count_files(self, resource_id: uuid.UUID) -> int:
        """How many files this resource already holds, in any status.

        Counted against `MAX_FILES_PER_RESOURCE` and **never reported to the
        learner**: it enforces a bound rather than describing them. Archived files
        count, because they still occupy storage.
        """
        ...

    def list_files(
        self, *, resource_id: uuid.UUID, filters: ResourceFileFilters
    ) -> tuple[ResourceFileRecord, ...]:
        """This resource's files, newest first.

        Ordered here rather than by a caller, for the reason
        `curriculum_repository` records: a result set cannot be ordered after it
        has been sliced.
        """
        ...

    def find_file(self, file_id: uuid.UUID) -> ResourceFileRecord | None:
        """One file by identifier, whatever its status.

        Returns an archived file too. Ownership is checked by the use case
        against the resource this row names; this port answers what is stored.
        """
        ...

    def add_file(self, record: ResourceFileRecord) -> None:
        """Record a stored file."""
        ...

    def update_file(self, record: ResourceFileRecord) -> None:
        """Save a changed status. Nothing else about a stored file may move."""
        ...
