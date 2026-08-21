"""Input and output structures for the PDF files kept against a resource.

These carry what RES-014 to RES-017 return. They are framework-independent by
design, as the other DTOs in this package are.

**This is the first material LearnFlow stores as a file.**
[ADR-032](../../../../docs/adr/ADR-032-learning-resource-catalogue.md) kept three
things out — uploaded files, fetched web content, and locations on the learner's
own machine.
[ADR-037](../../../../docs/adr/ADR-037-learner-written-resource-notes.md) narrowed
the first of those for text the learner typed;
[ADR-040](../../../../docs/adr/ADR-040-learner-uploaded-resource-files.md) narrows
it for a PDF they choose in a file picker. **The other two stay out**: nothing is
fetched from the web, and **no filesystem path is ever accepted or returned** —
not the learner's, and not the server's.

**Bytes and metadata live apart.** A row here describes a file: what the learner
called it, how large it is, how many pages, and an opaque `storage_key`. The
bytes themselves live in a local volume behind a storage port, never in a column,
because a database is a poor place for binaries and a `bytea` would land in every
backup and every dump.

**Nothing derived is stored.** No extracted text, no chunk, no embedding, no
thumbnail, and no preview. The file is kept and read back; nothing reads *into*
it beyond counting its pages, and nothing else in LearnFlow changes.

**Nothing here is a measurement of the learner.** A page count and a byte size
describe a document, not the person who uploaded it, and neither is totalled,
ranked, or shown as progress.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

RESOURCE_FILE_STATUSES: tuple[str, ...] = ("active", "archived")
"""Every status a stored file may hold.

Two, mirroring `RESOURCE_NOTE_STATUSES` exactly. **Neither deletes anything**: a
learner sets a file aside reversibly, and the bytes stay where they are. The
ingestion states `processing`, `ready`, and `failed` are deliberately absent —
nothing extracts anything, so a file could enter one and never leave.
"""

ACTIVE = "active"
ARCHIVED = "archived"

MAX_FILE_BYTES = 25 * 1024 * 1024
"""How large one PDF may be, in bytes.

Twenty-five megabytes holds a scanned textbook chapter or a full previous-year
paper while bounding a single request. It is checked **while the upload streams**,
so an oversized file is refused before it is held in memory in full — the reason
this is a limit rather than a guideline.

An application rule over a filesystem that would accept anything, so raising it
needs no migration.
"""

MAX_PAGE_COUNT = 1_500
"""How many pages one PDF may have.

Enough for a whole textbook. It exists because page count, unlike byte size, is
what predicts the cost of anything that later reads the document, and refusing a
runaway file now is cheaper than discovering it then.
"""

MAX_FILES_PER_RESOURCE = 20
"""How many files one resource may carry.

A bounded collection, the rule `MAX_NOTES_PER_RESOURCE` already sets for notes.
It is **never reported** to the learner as a figure — they are told what they may
add, not how close they are to a ceiling.
"""

MAX_FILENAME_LENGTH = 255
"""How long a learner's own filename may be, as metadata.

The stored name on disk is a server-generated identifier and is unaffected by
this; the original is kept only so a download can be offered under the name the
learner recognises.
"""

PDF_CONTENT_TYPE = "application/pdf"
"""The only content type this feature stores.

Sent back on download. It is decided by LearnFlow from what it validated, never
echoed from what a caller claimed.
"""

PDF_MAGIC = b"%PDF-"
"""The bytes every PDF begins with.

Checked against the file's actual content, because an extension is a claim and
this is evidence.
"""


class ResourceFileRejection(Enum):
    """Why an upload was refused.

    Named cases rather than one message, because they ask the learner to do
    different things: choose a different file, unlock it, or remove one first.

    **No member carries the filename or any byte of the file.** A refusal names
    the rule, which is docs/api/conventions.md's requirement and matters most
    where the data is a learner's own study material.
    """

    NOT_A_PDF = "not_a_pdf"
    """The extension or the leading bytes say this is not a PDF."""

    UNREADABLE = "unreadable"
    """It claims to be a PDF and could not be parsed."""

    ENCRYPTED = "encrypted"
    """It is password-protected, so LearnFlow cannot read it.

    Refused rather than stored: keeping a file it can never open would be storing
    something on a promise it cannot meet.
    """

    TOO_LARGE = "too_large"
    """Larger than `MAX_FILE_BYTES`."""

    TOO_MANY_PAGES = "too_many_pages"
    """More pages than `MAX_PAGE_COUNT`."""

    EMPTY = "empty"
    """No bytes were received at all."""


@dataclass(frozen=True, slots=True)
class PdfFacts:
    """What inspecting a PDF establishes, before anything is stored.

    Deliberately small. This feature reads a document's **structure** and never
    its content: there is no text field here, and nothing extracts one.
    """

    page_count: int
    is_encrypted: bool


@dataclass(frozen=True, slots=True)
class ResourceFileRecord:
    """One PDF kept against one resource.

    Attributes:
        id: The file's identifier, and the only thing a caller ever names it by.
        resource_id: The material it belongs to. Ownership is the resource's.
        storage_key: Where the bytes are, as the storage port understands it.
            **Opaque, and never returned by any endpoint** — it is an internal
            reference, and a resource endpoint may not expose a storage location.
        original_filename: What the learner called the file, kept so a download
            can be offered under a name they recognise. **Never used as a path.**
        byte_size: How large it is.
        page_count: How many pages it has.
        content_type: Always `application/pdf`, decided from what was validated.
        checksum: A SHA-256 of the bytes, so corruption and duplication are
            detectable without reading the file back in full.
        status: `active` or `archived`. Archiving hides and never removes.
        created_at: When it was stored.
        updated_at: When its status last moved.
    """

    id: uuid.UUID
    resource_id: uuid.UUID
    storage_key: str
    original_filename: str
    byte_size: int
    page_count: int
    content_type: str
    checksum: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ResourceFileContent:
    """One file's bytes, with what a download needs to describe them.

    Held in memory for the length of one response. That is a deliberate bound on
    this feature rather than an oversight: `MAX_FILE_BYTES` caps what can be here,
    and streaming from the storage port is the change to make if that ceiling ever
    rises.
    """

    record: ResourceFileRecord
    content: bytes


@dataclass(frozen=True, slots=True)
class ResourceFileFilters:
    """Which of a resource's files a read should return.

    `statuses` empty means every status, the shape the note and resource filters
    already use.
    """

    statuses: tuple[str, ...] = ()
