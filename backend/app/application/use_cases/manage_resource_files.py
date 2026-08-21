"""Keeping a learner's own PDF files against a piece of their study material.

Serves RES-014 to RES-017, contracted by
[ADR-040](../../../../docs/adr/ADR-040-learner-uploaded-resource-files.md). It is
the first code in LearnFlow that stores a **file**.

**It stores and reads back, and does nothing else.** Nothing extracts text, runs
OCR, chunks, embeds, indexes, summarises, or searches. Nothing reaches the
network: no URL is fetched, no cloud storage is written, and no AI provider is
bound — a test asserts the constructor's collaborators, so adding one would be a
visible decision rather than a quiet one.

**Validation happens before anything is stored.** A file is checked, then
written; a refused upload leaves **no row and no bytes**, so a rejection cannot
half-succeed. The order matters and is asserted: size, then signature, then
structure, then page count.

**No path is accepted or returned, ever.** The learner picks a file in a browser
and the bytes arrive; LearnFlow never learns where it sat on their machine, and
never reveals where it put it. `storage_key` stays inside this layer and its
adapters.

**Nothing is deleted.** A file is set aside with `archived` and comes back
unchanged; there is no removal method on either port, so this use case could not
delete a byte if asked. Permanent deletion is RES-005, and it must coordinate
bytes and rows together.

**Ownership is the resource's.** A file is reached through the resource it
belongs to, and that resource must belong to the effective learner — the rule
`ManageResourceNotes` already applies to notes.
"""

import hashlib
import uuid

from app.application.dto.resource import ResourceRecord
from app.application.dto.resource_file import (
    ACTIVE,
    MAX_FILE_BYTES,
    MAX_FILENAME_LENGTH,
    MAX_FILES_PER_RESOURCE,
    MAX_PAGE_COUNT,
    PDF_CONTENT_TYPE,
    PDF_MAGIC,
    RESOURCE_FILE_STATUSES,
    PdfFacts,
    ResourceFileContent,
    ResourceFileFilters,
    ResourceFileRecord,
    ResourceFileRejection,
)
from app.application.ports.learner_repository import LearnerRepository
from app.application.ports.resource_file_storage import (
    DocumentInspector,
    ResourceFileRepository,
    ResourceFileStorage,
)
from app.application.ports.resource_repository import ResourceRepository
from app.application.use_cases.local_learner import resolve_local_learner

REGISTERED = "registered"
"""The resource status that accepts new files.

Archived material is read-only, notes included — RES-004's rule, applied to files
so that putting something aside means one thing everywhere.
"""


class ResourceFileError(Exception):
    """Base class for the refusals this use case makes."""


class LearnerNotSetUpError(ResourceFileError):
    """No learner is stored, so no material belongs to anyone."""


class UnknownResourceError(ResourceFileError):
    """A resource identifier naming nothing this learner owns."""


class UnknownResourceFileError(ResourceFileError):
    """A file identifier naming nothing this learner owns."""


class ResourceNotWritableError(ResourceFileError):
    """The resource is archived, so its files may not be added to or changed."""


class TooManyFilesError(ResourceFileError):
    """This resource already holds `MAX_FILES_PER_RESOURCE` files."""


class UnsupportedFileError(ResourceFileError):
    """The file itself was refused.

    Carries a `ResourceFileRejection` so a route can map the reason to words a
    learner can act on. **The message never contains the filename or any byte of
    the file.**
    """

    def __init__(self, rejection: ResourceFileRejection, message: str) -> None:
        """Record which rule refused this file."""
        super().__init__(message)
        self.rejection = rejection


class InvalidFileStatusError(ResourceFileError):
    """A status this build does not store."""


class ManageResourceFiles:
    """Stores, lists, reads back, and sets aside a resource's PDF files.

    It binds five collaborators: learners, to resolve who is asking; resources,
    to check the material is theirs and still writable; the file repository, for
    rows; the storage port, for bytes; and an inspector that reads a PDF's
    structure.

    **No AI provider, embedding provider, retrieval provider, or HTTP client is
    bound**, and a test asserts it. A learner's file has no path out of this
    process.
    """

    def __init__(
        self,
        *,
        learners: LearnerRepository,
        resources: ResourceRepository,
        files: ResourceFileRepository,
        storage: ResourceFileStorage,
        inspector: DocumentInspector,
    ) -> None:
        """Bind the use case to its ports."""
        self._learners = learners
        self._resources = resources
        self._files = files
        self._storage = storage
        self._inspector = inspector

    def store_file(
        self, *, resource_id: uuid.UUID, filename: str, content: bytes
    ) -> ResourceFileRecord:
        """Validate a PDF and keep it against this resource (RES-014).

        **Nothing is written until every check has passed.** The bytes go to the
        storage port only after the file has been accepted, so a refusal leaves
        no row and no file behind.

        Raises:
            LearnerNotSetUpError: No learner is stored yet.
            UnknownResourceError: The resource is not this learner's.
            ResourceNotWritableError: The resource is archived.
            TooManyFilesError: The resource already holds the maximum.
            UnsupportedFileError: The file failed a validation rule.
        """
        resource = self._writable_resource(resource_id)

        if self._files.count_files(resource.id) >= MAX_FILES_PER_RESOURCE:
            raise TooManyFilesError(
                f"A resource may hold at most {MAX_FILES_PER_RESOURCE} files. "
                "Set one aside before adding another."
            )

        facts = _validate_pdf(filename, content, self._inspector)
        storage_key = self._storage.store(content=content)

        record = ResourceFileRecord(
            id=uuid.uuid4(),
            resource_id=resource.id,
            storage_key=storage_key,
            original_filename=_readable_filename(filename),
            byte_size=len(content),
            page_count=facts.page_count,
            content_type=PDF_CONTENT_TYPE,
            checksum=hashlib.sha256(content).hexdigest(),
            status=ACTIVE,
        )
        self._files.add_file(record)
        return record

    def list_files(
        self, *, resource_id: uuid.UUID, statuses: tuple[str, ...] = ()
    ) -> tuple[ResourceFileRecord, ...]:
        """This resource's files, newest first (RES-015).

        Readable whatever the resource's own status: archived material stays
        **readable** and only stops being writable, which is the rule notes
        already follow.

        Raises:
            LearnerNotSetUpError: No learner is stored yet.
            UnknownResourceError: The resource is not this learner's.
            InvalidFileStatusError: A status this build does not store.
        """
        resource = self._owned_resource(resource_id)
        for status in statuses:
            if status not in RESOURCE_FILE_STATUSES:
                raise InvalidFileStatusError(
                    f"{status!r} is not a stored file status. "
                    f"Use one of {', '.join(RESOURCE_FILE_STATUSES)}."
                )
        return self._files.list_files(
            resource_id=resource.id, filters=ResourceFileFilters(statuses=tuple(statuses))
        )

    def read_file(self, file_id: uuid.UUID) -> ResourceFileContent:
        """One file's bytes, for the learner who owns it (RES-016).

        **An archived file is still readable.** Setting material aside is
        shelving, not withholding: the learner owns the file, and hiding it from
        a list is not a reason to refuse it to them.

        Raises:
            LearnerNotSetUpError: No learner is stored yet.
            UnknownResourceFileError: No such file, it is not this learner's, or
                its bytes are missing from storage.
        """
        record = self._owned_file(file_id)
        content = self._storage.read(record.storage_key)
        if content is None:
            # A row without bytes: a volume restored from a backup older than the
            # database would look exactly like this. Reported as missing rather
            # than as a server fault, and the storage key stays internal.
            raise UnknownResourceFileError(
                f"The stored file {file_id} is recorded but its content is not in storage."
            )
        return ResourceFileContent(record=record, content=content)

    def set_file_status(self, *, file_id: uuid.UUID, status: str) -> ResourceFileRecord:
        """Set a file aside, or bring it back (RES-017).

        Reversible in both directions, and **nothing is removed** either way.

        Raises:
            LearnerNotSetUpError: No learner is stored yet.
            UnknownResourceFileError: The file is not this learner's.
            ResourceNotWritableError: Its resource is archived.
            InvalidFileStatusError: A status this build does not store.
        """
        if status not in RESOURCE_FILE_STATUSES:
            raise InvalidFileStatusError(
                f"{status!r} is not a stored file status. "
                f"Use one of {', '.join(RESOURCE_FILE_STATUSES)}."
            )
        record = self._owned_file(file_id)
        self._writable_resource(record.resource_id)

        if record.status == status:
            return record
        moved = ResourceFileRecord(
            id=record.id,
            resource_id=record.resource_id,
            storage_key=record.storage_key,
            original_filename=record.original_filename,
            byte_size=record.byte_size,
            page_count=record.page_count,
            content_type=record.content_type,
            checksum=record.checksum,
            status=status,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        self._files.update_file(moved)
        return moved

    # -- resolving what the learner owns --------------------------------------

    def _owned_resource(self, resource_id: uuid.UUID) -> ResourceRecord:
        """The resource, if this learner owns it."""
        learner = resolve_local_learner(self._learners)
        if learner is None:
            raise LearnerNotSetUpError("No learner is stored, so no material belongs to anyone.")

        resource = self._resources.find_resource(resource_id)
        if resource is None or resource.owner_learner_id != learner.id:
            # A resource belonging to somebody else is reported as missing rather
            # than as forbidden: telling a caller that an identifier exists but is
            # not theirs is itself a disclosure.
            raise UnknownResourceError(f"No resource is stored with identifier {resource_id}.")
        return resource

    def _writable_resource(self, resource_id: uuid.UUID) -> ResourceRecord:
        """The resource, if this learner owns it and has not put it aside."""
        resource = self._owned_resource(resource_id)
        if resource.status != REGISTERED:
            raise ResourceNotWritableError(
                "This material is archived, so its files cannot be changed. Bring it back first."
            )
        return resource

    def _owned_file(self, file_id: uuid.UUID) -> ResourceFileRecord:
        """The file, if it hangs off a resource this learner owns."""
        record = self._files.find_file(file_id)
        if record is None:
            raise UnknownResourceFileError(f"No stored file has identifier {file_id}.")
        # Ownership is the resource's, so it is checked there and never stored
        # a second time on the file row.
        try:
            self._owned_resource(record.resource_id)
        except UnknownResourceError as error:
            raise UnknownResourceFileError(f"No stored file has identifier {file_id}.") from error
        return record


def _validate_pdf(filename: str, content: bytes, inspector: DocumentInspector) -> PdfFacts:
    """Every rule a file must pass, in the order they are cheapest to apply.

    Size first, because it is a length check; then the signature, which reads
    five bytes; then the structure, which parses; then the page count, which the
    parse produced. A file that fails any of them is refused **before anything is
    written**.

    The extension is checked as a courtesy to the learner — it catches the wrong
    file in the picker with a clearer message than a parse failure — but it
    decides nothing on its own: the signature and the parse are the evidence.
    """
    if not content:
        raise UnsupportedFileError(
            ResourceFileRejection.EMPTY, "That file is empty, so there is nothing to store."
        )
    if len(content) > MAX_FILE_BYTES:
        raise UnsupportedFileError(
            ResourceFileRejection.TOO_LARGE,
            f"A file may be at most {MAX_FILE_BYTES // (1024 * 1024)} MB.",
        )
    if not filename.lower().endswith(".pdf") or not content.startswith(PDF_MAGIC):
        raise UnsupportedFileError(
            ResourceFileRejection.NOT_A_PDF, "Only PDF files can be stored here."
        )

    facts = inspector.inspect_pdf(content)
    if facts is None:
        raise UnsupportedFileError(
            ResourceFileRejection.UNREADABLE,
            "That PDF could not be read. It may be damaged or incomplete.",
        )
    if facts.is_encrypted:
        raise UnsupportedFileError(
            ResourceFileRejection.ENCRYPTED,
            "That PDF is password-protected, so it cannot be stored. "
            "Save an unlocked copy and choose that instead.",
        )
    if facts.page_count > MAX_PAGE_COUNT:
        raise UnsupportedFileError(
            ResourceFileRejection.TOO_MANY_PAGES,
            f"A file may have at most {MAX_PAGE_COUNT} pages.",
        )
    return facts


def _readable_filename(filename: str) -> str:
    """The learner's own filename, reduced to something safe to store and show.

    **This is metadata, never a path.** The bytes are stored under an identifier
    the storage adapter invents, so nothing here can steer where a file lands.
    What this removes is therefore about *display*, not traversal: directory
    separators and control characters would otherwise render oddly or split a
    header on the way back out.
    """
    stripped = filename.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(
        character for character in stripped if character.isprintable() and character != '"'
    ).strip()
    return (cleaned or "document.pdf")[:MAX_FILENAME_LENGTH]
