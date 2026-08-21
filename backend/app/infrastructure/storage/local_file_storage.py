"""The local-volume adapter behind `ResourceFileStorage`, and the PDF inspector.

**The only file in LearnFlow that touches a filesystem.** Everything path-shaped
lives here: the root directory, the sharding, the naming, and the one place a
`storage_key` is turned back into a real location. Application code sees opaque
keys and never learns a path
([dependency rules](../../../../docs/architecture/dependency-rules.md)).

**Bytes land in a Docker named volume**, mounted only into the `backend` service
at `RESOURCE_STORAGE_PATH`. A named volume survives `docker compose down`, an
image rebuild, and container recreation; only `docker compose down -v` destroys
it, exactly as for `postgres_data`. Nothing here writes outside that root.

**A stored name is an identifier this module invents, never the learner's.** A
filename arriving from a browser is untrusted input: used as a path it invites
traversal, collisions, reserved Windows names, and unicode surprises. The
learner's own name is kept as metadata in PostgreSQL, where it is data rather
than a location.

**Keys are sharded two levels deep** (`ab/cd/<uuid>.pdf`) so that a learner with
thousands of files never leaves one directory holding all of them — a real
problem on both NTFS and ext4 for listing and for backup tools.

**Nothing here reads a document's content.** `PyPdfDocumentInspector` opens a PDF
to count pages and detect encryption, and returns neither text nor any part of
it. There is no extraction, no OCR, no rendering, and no thumbnail: this feature
stores files and reads them back.

**Nothing here deletes.** There is no removal method, because the port has none.
"""

import re
import uuid
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.application.dto.resource_file import PdfFacts

_KEY_PATTERN = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f-]{36}\.pdf$")
"""Exactly the shape this module issues.

A key is checked against it before being resolved to a path. Nothing else in the
application constructs one, so a value failing this arrived from somewhere it
should not have, and is refused rather than joined onto the storage root.
"""


class LocalResourceFileStorage:
    """Keeps file bytes under one directory, addressed by an opaque key.

    Args:
        root: The storage root, from `RESOURCE_STORAGE_PATH`. Created if absent,
            so a fresh volume needs no setup step.
    """

    def __init__(self, *, root: Path) -> None:
        """Bind the adapter to one storage root."""
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def store(self, *, content: bytes) -> str:
        """Write these bytes under a newly invented key.

        The key is derived from a fresh UUID and nothing else — not the content,
        not the filename, and not the learner. Two identical uploads are two
        files, because deduplicating them would make one learner's archive action
        affect another record.
        """
        identifier = uuid.uuid4().hex
        key = f"{identifier[:2]}/{identifier[2:4]}/{uuid.UUID(identifier)}.pdf"
        destination = self._root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return key

    def read(self, storage_key: str) -> bytes | None:
        """The bytes behind a key, or `None` when nothing is there.

        The key is validated against the shape this module issues **before** it
        is joined to the root, so a crafted value cannot escape the storage
        directory. A missing file is `None`: a volume restored from a backup
        older than the database would look exactly like that, and it is a state
        the caller reports rather than a fault.
        """
        if not _KEY_PATTERN.match(storage_key):
            return None
        location = self._root / storage_key
        # Belt and braces: the pattern already forbids traversal, and this
        # confirms the resolved path really is inside the root.
        try:
            location.resolve().relative_to(self._root.resolve())
        except ValueError:
            return None
        if not location.is_file():
            return None
        return location.read_bytes()


class PyPdfDocumentInspector:
    """Reads a PDF's structure with `pypdf`, and never its content."""

    def inspect_pdf(self, content: bytes) -> PdfFacts | None:
        """How many pages this PDF has, and whether it is encrypted.

        Returns `None` for anything `pypdf` cannot open — malformed, truncated,
        or not a PDF at all — so the caller refuses it rather than storing a file
        LearnFlow cannot read.

        **No text is extracted.** `pypdf` is asked for the page count and the
        encryption flag; `extract_text` is deliberately never called, and a test
        asserts that this module does not reference it.

        An encrypted document is reported as encrypted rather than refused here:
        deciding what to do about it is the use case's rule, not this adapter's.
        """
        try:
            reader = PdfReader(BytesIO(content), strict=False)
            if reader.is_encrypted:
                # The page count of an encrypted document is not readable
                # without the password, so it is reported as zero and the caller
                # refuses on encryption before any count matters.
                return PdfFacts(page_count=0, is_encrypted=True)
            return PdfFacts(page_count=len(reader.pages), is_encrypted=False)
        except PyPdfError, ValueError, OSError, RecursionError, KeyError, TypeError:
            # pypdf raises a wide and version-dependent range on damaged input.
            # Everything here means the same thing to a learner -- the file could
            # not be read -- so they are caught together rather than distinguished
            # into messages nobody can act on differently.
            return None
