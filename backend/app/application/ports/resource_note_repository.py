"""The persistence port the resource-note endpoints work through.

It reads and writes the notes a learner keeps against one learning resource.
Ownership is **not** decided here: a note belongs to a resource, and the resource
belongs to a learner, so the use case reads the resource through
`ResourceRepository` and compares. Reading both through ports of their own keeps
this one to the rows it actually owns.

Ordering of a page is fixed here, for the reason `curriculum_repository` records:
a page cannot be ordered after it has been sliced. Notes are ordered newest
first, which is the order every other learner-owned collection uses.

Nothing here deletes. A note is put aside by moving its status, and that is
reversible, so no removal method exists to be called by mistake.
"""

import uuid
from typing import Protocol

from app.application.dto.resource_note import ResourceNoteFilters, ResourceNoteRecord


class ResourceNoteRepository(Protocol):
    """Reads and writes the notes kept against a learner's learning resources."""

    def count_notes(self, *, resource_id: uuid.UUID, filters: ResourceNoteFilters) -> int:
        """How many of this resource's notes match, for the pagination block."""
        ...

    def count_all_notes(self, resource_id: uuid.UUID) -> int:
        """How many notes this resource holds, whatever their status.

        Read only to decide whether one more may be written, against
        `MAX_NOTES_PER_RESOURCE`. **It is never reported**: a figure beside a
        learner's material would measure the learner, which
        docs/domain/terminology.md permits for a plan's own coverage and for one
        scheduling request and nowhere else.

        Notes put aside are counted, because a bound that ignored them could be
        stepped around by archiving.
        """
        ...

    def list_notes(
        self,
        *,
        resource_id: uuid.UUID,
        filters: ResourceNoteFilters,
        limit: int,
        offset: int,
    ) -> tuple[ResourceNoteRecord, ...]:
        """One page of the resource's notes, newest first."""
        ...

    def find_note(self, note_id: uuid.UUID) -> ResourceNoteRecord | None:
        """The note with this identifier, or None.

        Ownership is a rule, so the use case decides it. This returns the record
        whichever resource holds it, and the caller checks that resource.
        """
        ...

    def add_note(self, record: ResourceNoteRecord) -> None:
        """Store a new note. The caller owns the transaction."""
        ...

    def delete_note(self, note_id: uuid.UUID) -> None:
        """Remove a note. **Permanent, and the row is all there is.**

        Nothing derived from a note is stored -- no chunk, no embedding, no
        cached extract -- so unlike a stored file there is no second thing to
        clean up, and deleting one cannot leave anything orphaned. See
        [ADR-041](../../../../docs/adr/ADR-041-removing-a-stored-file-or-note.md).

        Deleting a note this does not hold is not an error: the operation must be
        safe to repeat.
        """
        ...

    def update_note(self, record: ResourceNoteRecord) -> None:
        """Store a changed note. The caller owns the transaction."""
        ...
