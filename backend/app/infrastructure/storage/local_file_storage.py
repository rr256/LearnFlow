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

**Removal is the one destructive thing here**, and it unlinks a single file
within the storage root. It never removes a directory: an empty shard costs
nothing, and a routine that prunes directories is a routine that can delete more
than it was asked to.
"""

import re
import uuid
from io import BytesIO
from pathlib import Path

from pypdf import PasswordType, PdfReader

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
        root: The storage root, from `RESOURCE_STORAGE_PATH`. Created on first
            write, so a fresh volume needs no setup step.
    """

    def __init__(self, *, root: Path) -> None:
        """Bind the adapter to one storage root.

        **Constructing this touches no filesystem.** The root is created on the
        first write instead, because the composition root builds this adapter at
        startup: creating a directory here would make the whole application fail
        to start wherever that path is not writable — on a CI runner, in a
        read-only container, or on any machine that has never uploaded a file.
        Startup must not depend on a capability nothing has asked for yet.
        """
        self._root = root

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
        # `parents=True` creates the storage root as well as the two shard
        # directories, which is what makes construction side-effect free.
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return key

    def remove(self, storage_key: str) -> None:
        """Delete the bytes behind a key, if they are there.

        The key is validated against the shape this module issues **before** it is
        joined to the root, exactly as `read` does, so a crafted value cannot
        reach outside the storage directory. Anything failing that check is
        ignored rather than acted on.

        **A missing file is success, not an error.** Deletion must be safe to
        repeat: a retry after a partial failure, and a row whose bytes a restore
        already lost, both have to end in the same place. Every other failure —
        a permission error, a read-only mount — is raised, which is what rolls
        the caller's still-open transaction back.

        The containing directories are deliberately left behind. An empty shard
        costs nothing, and pruning is how a delete routine grows into one that
        removes more than it was asked to.
        """
        located = self._within_root(storage_key)
        if located is None:
            return
        located.unlink(missing_ok=True)

    def read(self, storage_key: str) -> bytes | None:
        """The bytes behind a key, or `None` when nothing is there.

        The key is validated against the shape this module issues **before** it
        is joined to the root, so a crafted value cannot escape the storage
        directory. A missing file is `None`: a volume restored from a backup
        older than the database would look exactly like that, and it is a state
        the caller reports rather than a fault.
        """
        located = self._within_root(storage_key)
        if located is None or not located.is_file():
            return None
        return located.read_bytes()

    def _within_root(self, storage_key: str) -> Path | None:
        """The real path a key names, or `None` when it names nothing legitimate.

        Shared by `read` and `remove` so both are guarded identically -- a second
        copy of this check is a second place for it to drift, and `remove` is the
        one that would be destructive if it did.
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
        return location


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
            if reader.is_encrypted and not _opens_without_a_password(reader):
                # Genuinely locked: LearnFlow cannot read it, so the page count
                # is unknowable and the caller refuses on encryption.
                return PdfFacts(page_count=0, is_encrypted=True)
            return PdfFacts(page_count=len(reader.pages), is_encrypted=False)
        except Exception:
            # **Deliberately broad, and this is the right boundary for it.**
            #
            # This method's whole contract is "the facts, or None when the
            # document cannot be read", and it is parsing a file LearnFlow did
            # not produce. pypdf's raise surface is wide, version-dependent, and
            # not rooted in one base class: `DependencyError` extends `Exception`
            # directly rather than `PyPdfError`, so an earlier, tidier tuple of
            # named exceptions let it through and an unreadable PDF became a 500
            # rather than a refusal the learner could act on.
            #
            # Every failure here means the same thing to a learner -- this file
            # could not be read -- so they are answered the same way. The caller
            # refuses the upload, and nothing is stored, so a swallowed exception
            # cannot leave anything half-written.
            return None


def _opens_without_a_password(reader: PdfReader) -> bool:
    """Whether an encrypted document opens with an **empty** user password.

    **Most encrypted study material is not locked.** A publisher or scanned PDF
    is commonly encrypted with an empty user password and carries only permission
    restrictions -- no printing, no copying. It opens in any reader, and LearnFlow
    can read and store it exactly like any other file.

    `is_encrypted` alone cannot tell that apart from a document that genuinely
    needs a password, which is why this attempt exists. It reads ADR-040's rule
    as **refuse what LearnFlow cannot open**, which is the reason that rule gives.

    **Nothing is decrypted on disk.** The attempt unlocks the in-memory reader so
    the page count can be read; the bytes LearnFlow stores are the learner's
    original file, unchanged.

    Returns `False` on any failure, including a missing crypto backend, so an
    undecidable document is treated as locked rather than assumed readable.
    """
    try:
        return reader.decrypt("") != PasswordType.NOT_DECRYPTED
    except Exception:
        return False
