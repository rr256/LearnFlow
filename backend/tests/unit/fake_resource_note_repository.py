"""An in-memory stand-in for the resource-note repository port.

Notes are held in the order they were written and returned newest first, matching
the order the port fixes and the SQLAlchemy adapter applies — so a use case
relying on the store to sort fails here rather than passing by accident.

The controlled value is asserted on write, mirroring the database `CHECK`: a fake
accepting a status PostgreSQL would refuse would let a use-case test pass on a
shape the real database cannot store. The non-empty-body check is asserted for
the same reason.

**There is no removal method**, because the port has none: a note is put aside by
moving its status, and nothing in LearnFlow deletes one. A test that expected a
delete would fail to find one here, which is the point.
"""

import uuid
from collections.abc import Sequence

from app.application.dto.resource_note import (
    RESOURCE_NOTE_STATUSES,
    ResourceNoteFilters,
    ResourceNoteRecord,
)


class FakeResourceNoteRepository:
    """Stores resource notes in a list, newest last."""

    def __init__(self, notes: Sequence[ResourceNoteRecord] = ()) -> None:
        """Start from any notes already written."""
        self.notes = list(notes)

    def count_notes(self, *, resource_id: uuid.UUID, filters: ResourceNoteFilters) -> int:
        return len(self._matching(resource_id, filters))

    def count_all_notes(self, resource_id: uuid.UUID) -> int:
        return len([note for note in self.notes if note.resource_id == resource_id])

    def list_notes(
        self,
        *,
        resource_id: uuid.UUID,
        filters: ResourceNoteFilters,
        limit: int,
        offset: int,
    ) -> tuple[ResourceNoteRecord, ...]:
        return tuple(self._matching(resource_id, filters)[offset : offset + limit])

    def find_note(self, note_id: uuid.UUID) -> ResourceNoteRecord | None:
        return next((note for note in self.notes if note.id == note_id), None)

    def add_note(self, record: ResourceNoteRecord) -> None:
        self._require_storable(record)
        if any(stored.id == record.id for stored in self.notes):
            raise AssertionError(f"Note {record.id} is already stored.")
        self.notes.append(record)

    def update_note(self, record: ResourceNoteRecord) -> None:
        self._require_storable(record)
        for index, stored in enumerate(self.notes):
            if stored.id == record.id:
                if stored.resource_id != record.resource_id:
                    raise AssertionError("A note cannot be moved to another resource.")
                self.notes[index] = record
                return
        raise LookupError(f"No note is stored with identifier {record.id}.")

    def _matching(
        self, resource_id: uuid.UUID, filters: ResourceNoteFilters
    ) -> list[ResourceNoteRecord]:
        matched = [note for note in self.notes if note.resource_id == resource_id]
        if filters.status is not None:
            matched = [note for note in matched if note.status == filters.status]
        # Newest first, as the port fixes. Insertion order stands in for
        # `created_at`, which the record does not carry.
        return list(reversed(matched))

    @staticmethod
    def _require_storable(record: ResourceNoteRecord) -> None:
        """Refuse what the database's CHECK constraints would refuse."""
        if record.status not in RESOURCE_NOTE_STATUSES:
            raise AssertionError(f"'{record.status}' is not a stored note status.")
        if not record.body.strip():
            raise AssertionError("A stored note must have text in it.")
