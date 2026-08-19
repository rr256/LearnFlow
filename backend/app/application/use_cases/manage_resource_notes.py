"""Keeping a learner's own notes against the material they study from.

Serves RES-009 to RES-012, which extend
[FR-007](../../../docs/requirements/functional.md#fr-007-learning-resource-organization)
and lay the first foundation for
[FR-008](../../../docs/requirements/functional.md#fr-008-grounded-mentor-assistance).

**This is the first study material LearnFlow stores rather than points at**, and the
boundary around it is narrow and deliberate. A note is text the learner **typed
or pasted themselves**: their own notes on a piece of material, or a passage they
transcribed from it. Nothing here uploads a file, fetches an address, downloads a
page, extracts text from a document, runs OCR, or reads anything from the
learner's machine. `resources.storage_key`, `resources.metadata`, and
`resource_ingestions` all remain absent, and RES-005 to RES-008 remain
unimplemented.

**Nothing is sent anywhere.** This use case binds no AI provider, no embedding
provider, and no retrieval provider, and it makes no outbound call of any kind —
there is no port here through which a note could leave the process. Nothing
chunks a note, embeds it, indexes it, searches across notes, or answers a
question from one. Those arrive with the ingestion and retrieval change, and
adding a provider port to this constructor is the visible decision that would
begin it (NFR-001).

**The text is stored as the learner wrote it.** Line terminators are
canonicalised and surrounding whitespace is removed; nothing else is touched.
That canonicalisation undoes a choice the *transport* made rather than one the
learner did — the HTML form-data encoding algorithm normalises newlines, so a
form posted with JavaScript disabled would otherwise store the same note
differently from one posted through a hydrated server action. See
`_require_body`.

**The learner's text is never echoed back in a refusal.** Every rejection below
names the field and says what the rule is; none quotes the value, per
docs/api/conventions.md. That convention matters more here than anywhere else in
the product, because the value being refused is the learner's own study material.

**Nothing is deleted.** A note the learner is finished with is `archived`, and
archiving is reversible, which is ADR-032's position for a resource applied to
the text kept against one.

**A resource put aside is read-only**, notes included: a learner puts the
material back before writing or correcting a note on it. That is RES-004's rule
for archived material and ADR-035's for a retired question, and both are `409`.

**Nothing is recommended, ranked, scored, or counted.** A resource's notes are
the ones the learner wrote, in the order they wrote them, newest first. No note
is suggested, promoted above another, or counted on any response or screen —
`MAX_NOTES_PER_RESOURCE` is read to decide whether one more may be written and
reaches nothing a learner sees.

**Nothing else moves.** Writing, correcting, or putting aside a note writes no
resource, no topic link, no learning stage, no plan, no plan item, no revision,
and no quiz.
"""

import uuid
from collections.abc import Sequence

from app.application.dto.resource import ARCHIVED as RESOURCE_ARCHIVED
from app.application.dto.resource import ResourceRecord
from app.application.dto.resource_note import (
    ACTIVE,
    MAX_NOTE_BODY_LENGTH,
    MAX_NOTE_TITLE_LENGTH,
    MAX_NOTES_PER_RESOURCE,
    RESOURCE_NOTE_STATUSES,
    NewResourceNote,
    ResourceNoteChanges,
    ResourceNoteDetail,
    ResourceNoteFilters,
    ResourceNotePage,
    ResourceNoteRecord,
)
from app.application.ports.learner_repository import LearnerRepository
from app.application.ports.resource_note_repository import ResourceNoteRepository
from app.application.ports.resource_repository import ResourceRepository
from app.application.use_cases.local_learner import resolve_local_learner

CR = "\r"
LF = "\n"
CRLF = "\r\n"
"""The line terminators a note's text may arrive with.

Named rather than written inline, because the difference between them is the
whole point of the canonicalisation in `_require_body`, and an inline escape
is easy to misread.
"""


class ResourceNoteError(Exception):
    """Base class for the refusals this use case makes."""


class ResourceNotFoundError(ResourceNoteError):
    """No such resource is stored, or it belongs to another learner."""


class ResourceNoteNotFoundError(ResourceNoteError):
    """No such note is stored, or its resource belongs to another learner."""


class ArchivedResourceError(ResourceNoteError):
    """A note cannot be written or changed on material that is put aside.

    Read from what is **stored**, never from the request: a learner bringing a
    resource back and correcting a note in one request is doing two things, and
    RES-004 is where the first of them lives. The same refusal ADR-035 makes for
    a retired question.
    """


class MissingNoteTitleError(ResourceNoteError):
    """A note with no title, which nothing could find again without opening it."""


class MissingNoteBodyError(ResourceNoteError):
    """A note with no text in it."""


class NoteTitleTooLongError(ResourceNoteError):
    """A title longer than a label should be."""


class NoteTooLongError(ResourceNoteError):
    """More text than one note may hold.

    The bound exists so that a single request cannot fill the database and a
    single record cannot make a screen unrenderable. The refusal never quotes the
    text it rejected.
    """


class TooManyNotesError(ResourceNoteError):
    """More notes on one resource than it may hold."""


class UnknownNoteStatusError(ResourceNoteError):
    """A status a learner may not ask for."""


class EmptyNoteUpdateError(ResourceNoteError):
    """An update naming no field to change."""


class ManageResourceNotes:
    """Writes, reads, and changes the notes kept against a learner's resources.

    One use case serves all four endpoints, so the rule deciding whether a note
    belongs to the effective learner stays in one place — the reason
    `ManageResources` serves the catalogue endpoints together.

    It binds three ports and **no provider**: the learner repository to resolve
    who is asking, the resource repository to check that the material is theirs
    and still in the catalogue, and the note repository. There is nothing here
    through which a learner's text could leave the process.
    """

    def __init__(
        self,
        *,
        learners: LearnerRepository,
        resources: ResourceRepository,
        notes: ResourceNoteRepository,
    ) -> None:
        """Bind the use case to its ports."""
        self._learners = learners
        self._resources = resources
        self._notes = notes

    def add(self, resource_id: uuid.UUID, new_note: NewResourceNote) -> ResourceNoteDetail:
        """Keep one note against a piece of the learner's study material.

        The caller owns the transaction: this writes through the repository but
        never commits.

        The text is stored **as the learner wrote it**: line terminators are
        canonicalised and surrounding whitespace is removed, and nothing else is
        touched, so their line breaks, blank lines, indentation, and wording are
        preserved. docs/rag/ingestion.md normalises extracted
        text before chunking it, but that step belongs to a pipeline reading
        files, and rewriting what a learner typed would change what they wrote.

        Raises:
            ResourceNotFoundError: No such resource, or it is not the learner's.
            ArchivedResourceError: The material is put aside, so it is read-only.
            MissingNoteTitleError: The title is empty.
            MissingNoteBodyError: The note has no text in it.
            NoteTitleTooLongError: The title is longer than a label should be.
            NoteTooLongError: The text is longer than one note may hold.
            TooManyNotesError: The resource already holds as many notes as it may.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        resource = self._require_own_resource(resource_id)
        _require_material_in_the_catalogue(resource)

        # Read to decide whether one more note may be written, and for nothing
        # else. It reaches no response and no screen.
        if self._notes.count_all_notes(resource.id) >= MAX_NOTES_PER_RESOURCE:
            raise TooManyNotesError(
                f"This material already holds {MAX_NOTES_PER_RESOURCE} notes, which is as "
                "many as one piece may have. Add the next one to another piece of material."
            )

        record = ResourceNoteRecord(
            id=uuid.uuid4(),
            resource_id=resource.id,
            title=_require_title(new_note.title),
            body=_require_body(new_note.body),
            # Every note is written active. Putting one aside is a later
            # statement the learner makes, never a state anything starts in.
            status=ACTIVE,
        )
        self._notes.add_note(record)
        return _detail(record)

    def list_notes(
        self,
        resource_id: uuid.UUID,
        *,
        filters: ResourceNoteFilters,
        limit: int,
        offset: int,
    ) -> ResourceNotePage:
        """One page of a resource's notes, newest first.

        The notes of an **archived** resource are readable: putting material
        aside stops it being written to and takes it off the screens that show a
        topic's material, but it destroys nothing and hides nothing the learner
        goes looking for.

        Raises:
            ResourceNotFoundError: No such resource, or it is not the learner's.
            UnknownNoteStatusError: The status filter names an unknown state.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        if filters.status is not None:
            _require_known_status(filters.status)

        resource = self._require_own_resource(resource_id)
        records = self._notes.list_notes(
            resource_id=resource.id, filters=filters, limit=limit, offset=offset
        )
        return ResourceNotePage(
            notes=tuple(_details(records)),
            total=self._notes.count_notes(resource_id=resource.id, filters=filters),
        )

    def read(self, note_id: uuid.UUID) -> ResourceNoteDetail:
        """One of the learner's notes, exactly as they wrote it.

        Raises:
            ResourceNoteNotFoundError: No such note is stored, or its resource
                belongs to another learner.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        record, _ = self._require_own_note(note_id)
        return _detail(record)

    def update(self, note_id: uuid.UUID, changes: ResourceNoteChanges) -> ResourceNoteDetail:
        """Correct what a note says, or put it aside.

        The caller owns the transaction.

        A field the request omits is left alone. A note is corrected **in place**,
        as often as the learner likes: nothing reads a note, so no stored record
        can be made to disagree with a correction — the condition ADR-035 could
        not meet for a question a quiz had already asked.

        **Putting a note aside is reversible**, and it destroys nothing.

        Raises:
            ResourceNoteNotFoundError: No such note, or it is not the learner's.
            ArchivedResourceError: The material is put aside, so it is read-only.
            EmptyNoteUpdateError: The update names no field to change.
            MissingNoteTitleError: The new title is empty.
            MissingNoteBodyError: The new text is empty.
            NoteTitleTooLongError: The new title is too long.
            NoteTooLongError: The new text is longer than one note may hold.
            UnknownNoteStatusError: A status a learner may not ask for.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        if changes.is_empty:
            raise EmptyNoteUpdateError(
                "The request names no field to change. Send at least one of title, body, or status."
            )

        record, resource = self._require_own_note(note_id)
        _require_material_in_the_catalogue(resource)

        status = record.status
        if changes.status is not None:
            _require_known_status(changes.status)
            status = changes.status

        changed = ResourceNoteRecord(
            id=record.id,
            resource_id=record.resource_id,
            title=record.title if changes.title is None else _require_title(changes.title),
            body=record.body if changes.body is None else _require_body(changes.body),
            status=status,
        )
        self._notes.update_note(changed)
        return _detail(changed)

    def _require_own_resource(self, resource_id: uuid.UUID) -> ResourceRecord:
        """One of the learner's resources, or a refusal.

        Material owned by somebody else is reported as missing rather than as
        forbidden, the rule every learner-owned read follows: saying "that exists
        but is not yours" would confirm a record the caller may not read.
        """
        learner = resolve_local_learner(self._learners)
        record = None if learner is None else self._resources.find_resource(resource_id)
        if record is None or learner is None or record.owner_learner_id != learner.id:
            raise ResourceNotFoundError(
                f"No learning resource is stored with identifier {resource_id}."
            )
        return record

    def _require_own_note(self, note_id: uuid.UUID) -> tuple[ResourceNoteRecord, ResourceRecord]:
        """One of the learner's notes and the material it belongs to, or a refusal.

        A note is reached through its resource, so ownership is the resource's.
        Both refusals report the **note** as missing: a caller who may not read
        the note may not learn that its resource exists either.
        """
        learner = resolve_local_learner(self._learners)
        note = None if learner is None else self._notes.find_note(note_id)
        resource = None if note is None else self._resources.find_resource(note.resource_id)
        if (
            note is None
            or resource is None
            or learner is None
            or resource.owner_learner_id != learner.id
        ):
            raise ResourceNoteNotFoundError(f"No note is stored with identifier {note_id}.")
        return note, resource


def _details(records: Sequence[ResourceNoteRecord]) -> list[ResourceNoteDetail]:
    """Map stored records onto what a caller reads.

    Nothing is joined, counted, or looked up per record: a note names one
    resource and carries no topics of its own, so a page of them is one query
    and this mapping.
    """
    return [_detail(record) for record in records]


def _detail(record: ResourceNoteRecord) -> ResourceNoteDetail:
    """Map one stored record onto what a caller reads."""
    return ResourceNoteDetail(
        id=record.id,
        resource_id=record.resource_id,
        title=record.title,
        body=record.body,
        status=record.status,
    )


def _require_material_in_the_catalogue(resource: ResourceRecord) -> None:
    """Refuse a write against material the learner has put aside.

    Raises:
        ArchivedResourceError: The resource is archived.
    """
    if resource.status == RESOURCE_ARCHIVED:
        raise ArchivedResourceError(
            "This material is put aside, so its notes cannot be changed. Put it back in "
            "your catalogue first — nothing has been lost."
        )


def _require_title(title: str) -> str:
    """A note's title, or a refusal.

    Raises:
        MissingNoteTitleError: The title is empty or only whitespace.
        NoteTitleTooLongError: The title is longer than a label should be.
    """
    trimmed = title.strip()
    if not trimmed:
        raise MissingNoteTitleError(
            "A note needs a title, so you can find it again without opening it."
        )
    if len(trimmed) > MAX_NOTE_TITLE_LENGTH:
        raise NoteTitleTooLongError(
            f"A note's title can be at most {MAX_NOTE_TITLE_LENGTH} characters. "
            "Put the detail in the note itself."
        )
    return trimmed


def _require_body(body: str) -> str:
    """A note's text, or a refusal.

    Two things happen to the text and **nothing else**: line terminators are
    canonicalised to `LF`, and surrounding whitespace is removed. The learner's
    line breaks, blank lines, indentation, and wording are otherwise stored
    exactly as they typed them.

    **Canonicalising line terminators is not rewriting what the learner wrote.**
    It is undoing a choice the *transport* made. The HTML form-data encoding
    algorithm normalises newlines to `CRLF`, so a form posted with JavaScript
    disabled delivers `CRLF` where the same note submitted through a hydrated
    server action delivers `LF`. Without this, one note would be stored two
    different ways depending on whether a browser ran JavaScript, and a learner
    who wrote it one way and corrected it the other would find the stored text
    changing under them. A `CRLF` and an `LF` are the same line break, and the
    learner sees no difference either way.

    Found by the production standalone run with JavaScript disabled, which is
    the only check that submits a real multipart form.

    This is deliberately **not** docs/rag/ingestion.md's normalisation step,
    which collapses whitespace and strips extraction noise from text pulled out
    of a file. Nothing here touches a character the learner can see.

    Neither refusal quotes the text it rejected, per docs/api/conventions.md.

    Raises:
        MissingNoteBodyError: The note has no text in it.
        NoteTooLongError: The text is longer than one note may hold.
    """
    trimmed = body.replace(CRLF, LF).replace(CR, LF).strip()
    if not trimmed:
        raise MissingNoteBodyError(
            "A note needs some text in it. Write or paste what you want to keep."
        )
    if len(trimmed) > MAX_NOTE_BODY_LENGTH:
        raise NoteTooLongError(
            f"A note can hold at most {MAX_NOTE_BODY_LENGTH} characters, and this one is "
            "longer. Split it into a few shorter notes."
        )
    return trimmed


def _require_known_status(status: str) -> None:
    """Refuse a status a learner may not ask for.

    Raises:
        UnknownNoteStatusError: The status is outside `RESOURCE_NOTE_STATUSES`.
    """
    if status not in RESOURCE_NOTE_STATUSES:
        raise UnknownNoteStatusError(
            f"'{status}' is not a status you can set on a note. "
            f"Use one of: {', '.join(RESOURCE_NOTE_STATUSES)}."
        )
