"""In-memory stand-ins for the three ports stored files are reached through.

**Nothing here touches a filesystem.** A use-case test should fail on a rule, not
on a directory that could not be created, and a suite that wrote real files would
leave them behind on every run.

The fakes mirror the real adapters' contracts rather than being more generous
than them: `store` returns an opaque key the caller must not parse, `read`
returns `None` for an unknown key, and `inspect_pdf` returns `None` for anything
it cannot read.
"""

import uuid

from app.application.dto.resource_file import (
    PdfFacts,
    ResourceFileFilters,
    ResourceFileRecord,
)


class FakeResourceFileStorage:
    """Keeps bytes in a dictionary, addressed by an opaque key."""

    def __init__(self) -> None:
        """Start with nothing stored."""
        self.written: dict[str, bytes] = {}

    def store(self, *, content: bytes) -> str:
        key = f"{uuid.uuid4().hex[:2]}/{uuid.uuid4().hex[:2]}/{uuid.uuid4()}.pdf"
        self.written[key] = content
        return key

    def read(self, storage_key: str) -> bytes | None:
        return self.written.get(storage_key)


class FakeDocumentInspector:
    """Reports whatever a test set, without parsing anything.

    `unreadable` makes every inspection fail, which is how a malformed file is
    simulated without needing a genuinely corrupt PDF.
    """

    def __init__(
        self, *, page_count: int = 3, is_encrypted: bool = False, unreadable: bool = False
    ) -> None:
        """Start with a readable three-page document."""
        self.page_count = page_count
        self.is_encrypted = is_encrypted
        self.unreadable = unreadable
        self.inspected: list[bytes] = []

    def inspect_pdf(self, content: bytes) -> PdfFacts | None:
        self.inspected.append(content)
        if self.unreadable:
            return None
        return PdfFacts(page_count=self.page_count, is_encrypted=self.is_encrypted)


class FakeResourceFileRepository:
    """Holds file rows in a list, applying the same eligibility rules as the SQL."""

    def __init__(self, records: list[ResourceFileRecord] | None = None) -> None:
        """Start from stored rows, if a test supplied any."""
        self.records: list[ResourceFileRecord] = list(records or [])

    def count_files(self, resource_id: uuid.UUID) -> int:
        # Every status counts, as the real adapter does: an archived file still
        # occupies the volume.
        return len([r for r in self.records if r.resource_id == resource_id])

    def list_files(
        self, *, resource_id: uuid.UUID, filters: ResourceFileFilters
    ) -> tuple[ResourceFileRecord, ...]:
        found = [r for r in self.records if r.resource_id == resource_id]
        if filters.statuses:
            found = [r for r in found if r.status in filters.statuses]
        # Newest first, matching the adapter's ordering. Insertion order stands
        # in for `created_at`, which these fakes do not set.
        return tuple(reversed(found))

    def find_file(self, file_id: uuid.UUID) -> ResourceFileRecord | None:
        return next((r for r in self.records if r.id == file_id), None)

    def add_file(self, record: ResourceFileRecord) -> None:
        self.records.append(record)

    def update_file(self, record: ResourceFileRecord) -> None:
        for index, existing in enumerate(self.records):
            if existing.id == record.id:
                self.records[index] = record
                return


MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
)
"""Bytes that begin with the PDF signature.

Enough for the tests that exercise **application** rules, which never parse: the
fake inspector decides what a document is. Tests of the real adapter build real
PDFs instead.
"""
