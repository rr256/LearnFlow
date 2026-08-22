"""The local-volume adapter and the PDF inspector.

These use a **real filesystem** — `tmp_path`, never the configured volume — and a
**real `pypdf`**, because what they exist to prove is exactly what a fake cannot:
that bytes survive a round trip, that a crafted key cannot escape the storage
root, and that a genuinely damaged PDF is refused rather than stored.
"""

from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.infrastructure.storage.local_file_storage import (
    LocalResourceFileStorage,
    PyPdfDocumentInspector,
)


def a_pdf(pages: int = 2) -> bytes:
    """A real, valid PDF with the requested number of pages."""
    from io import BytesIO

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def storage(tmp_path: Path) -> LocalResourceFileStorage:
    """An adapter rooted in a directory this test owns."""
    return LocalResourceFileStorage(root=tmp_path / "resources")


# -- storing and reading back -------------------------------------------------


def test_bytes_survive_a_round_trip(storage: LocalResourceFileStorage):
    content = a_pdf()

    key = storage.store(content=content)

    assert storage.read(key) == content


def test_constructing_the_adapter_touches_no_filesystem(tmp_path: Path):
    """Startup must not depend on a capability nothing has asked for yet.

    The composition root builds this adapter when the application starts, so
    creating a directory in the constructor would make the whole process fail to
    start wherever the storage path is not writable — a CI runner, a read-only
    container, or a machine that has never uploaded a file.
    """
    root = tmp_path / "not" / "yet" / "there"

    LocalResourceFileStorage(root=root)

    assert not root.exists()


def test_the_root_is_created_on_the_first_write(tmp_path: Path):
    """A fresh volume still needs no setup step."""
    root = tmp_path / "not" / "yet" / "there"
    storage = LocalResourceFileStorage(root=root)

    key = storage.store(content=a_pdf())

    assert root.is_dir()
    assert storage.read(key) is not None


def test_reading_from_a_root_that_does_not_exist_reports_nothing(tmp_path: Path):
    """And does not create it, or raise."""
    root = tmp_path / "never" / "created"
    storage = LocalResourceFileStorage(root=root)

    assert storage.read("ab/cd/00000000-0000-4000-8000-000000000000.pdf") is None
    assert not root.exists()


def test_keys_are_sharded_two_levels_deep(storage: LocalResourceFileStorage):
    """So one directory never holds every file a learner owns."""
    key = storage.store(content=a_pdf())

    assert key.count("/") == 2
    assert key.endswith(".pdf")


def test_two_identical_uploads_get_different_keys(storage: LocalResourceFileStorage):
    content = a_pdf()

    first = storage.store(content=content)
    second = storage.store(content=content)

    assert first != second
    assert storage.read(first) == storage.read(second) == content


def test_a_key_names_no_part_of_any_filename(storage: LocalResourceFileStorage):
    """The adapter is never given a filename, so it cannot leak one."""
    key = storage.store(content=a_pdf())

    assert all(part.isalnum() or part in "-/." for part in key)


# -- a crafted key cannot escape the root ------------------------------------


@pytest.mark.parametrize(
    "crafted",
    [
        "../../../../etc/passwd",
        "..%2f..%2fsecret.pdf",
        "/etc/passwd",
        "ab/cd/../../../../secret.pdf",
        "C:\\Windows\\win.ini",
        "",
        "ab/cd/not-a-uuid.pdf",
        "ab/cd/00000000-0000-4000-8000-000000000000.exe",
    ],
)
def test_a_key_outside_the_issued_shape_reads_nothing(
    storage: LocalResourceFileStorage, crafted: str
):
    """Validated before it is joined to the root, not after."""
    assert storage.read(crafted) is None


def test_a_well_formed_key_for_a_file_that_is_not_there_reads_nothing(
    storage: LocalResourceFileStorage,
):
    """A volume restored from a backup older than the database looks like this."""
    assert storage.read("ab/cd/00000000-0000-4000-8000-000000000000.pdf") is None


def test_nothing_outside_the_root_is_readable(storage: LocalResourceFileStorage, tmp_path: Path):
    """Written beside the root, and unreachable through any key."""
    outsider = tmp_path / "outside.pdf"
    outsider.write_bytes(b"%PDF-secret")

    for attempt in ("../outside.pdf", "ab/../../outside.pdf"):
        assert storage.read(attempt) is None


# -- removal, the one destructive capability ---------------------------------


def test_removing_a_stored_file_deletes_its_bytes(storage: LocalResourceFileStorage):
    key = storage.store(content=a_pdf())

    storage.remove(key)

    assert storage.read(key) is None


def test_removing_the_same_file_twice_is_not_an_error(storage: LocalResourceFileStorage):
    """Deletion must be safe to repeat.

    The row is already gone by the time this runs, so raising on a second attempt
    would strand a file nothing can name.
    """
    key = storage.store(content=a_pdf())

    storage.remove(key)
    storage.remove(key)

    assert storage.read(key) is None


def test_removing_a_key_that_was_never_stored_is_not_an_error(
    storage: LocalResourceFileStorage,
):
    storage.remove("ab/cd/00000000-0000-4000-8000-000000000000.pdf")


def test_removing_one_file_leaves_the_others(storage: LocalResourceFileStorage):
    keep, remove = storage.store(content=a_pdf()), storage.store(content=a_pdf(pages=3))

    storage.remove(remove)

    assert storage.read(keep) is not None
    assert storage.read(remove) is None


@pytest.mark.parametrize(
    "crafted",
    [
        "../../../../etc/passwd",
        "/etc/passwd",
        "ab/cd/../../../../secret.pdf",
        r"C:\Windows\win.ini",
        "",
        "ab/cd/not-a-uuid.pdf",
    ],
)
def test_a_crafted_key_removes_nothing(
    storage: LocalResourceFileStorage, tmp_path: Path, crafted: str
):
    """The guard that matters most: `remove` is the destructive one.

    `read` and `remove` share one path check for exactly this reason -- a second
    copy is a second place for it to drift, and drift here deletes files.
    """
    outsider = tmp_path / "outside.pdf"
    outsider.write_bytes(b"%PDF-do-not-touch")
    kept = storage.store(content=a_pdf())

    storage.remove(crafted)

    assert outsider.read_bytes() == b"%PDF-do-not-touch"
    assert storage.read(kept) is not None


def test_removal_leaves_the_shard_directories_alone(
    storage: LocalResourceFileStorage, tmp_path: Path
):
    """Pruning is how a delete routine grows into one that removes too much."""
    key = storage.store(content=a_pdf())
    shard = (tmp_path / "resources" / key).parent

    storage.remove(key)

    assert shard.is_dir()


# -- inspecting a PDF ---------------------------------------------------------


def test_a_real_pdf_reports_its_page_count():
    facts = PyPdfDocumentInspector().inspect_pdf(a_pdf(pages=7))

    assert facts is not None
    assert facts.page_count == 7
    assert facts.is_encrypted is False


def an_encrypted_pdf(user_password: str, *, pages: int = 2, algorithm: str = "AES-256") -> bytes:
    """A real encrypted PDF, written with the algorithm real-world files use."""
    from io import BytesIO

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    writer.encrypt(user_password, algorithm=algorithm)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_a_password_locked_pdf_is_reported_as_encrypted():
    """LearnFlow cannot open it, so the caller refuses it."""
    facts = PyPdfDocumentInspector().inspect_pdf(an_encrypted_pdf("a-password"))

    assert facts is not None
    assert facts.is_encrypted is True
    assert facts.page_count == 0


def test_a_restricted_pdf_with_no_password_is_readable():
    """The case that made a learner's real file fail.

    A publisher or scanned PDF is commonly encrypted with an **empty** user
    password and carries only permission restrictions. It opens in any reader, so
    LearnFlow reads it and stores it like any other file.
    """
    facts = PyPdfDocumentInspector().inspect_pdf(an_encrypted_pdf("", pages=9))

    assert facts is not None
    assert facts.is_encrypted is False
    assert facts.page_count == 9


@pytest.mark.parametrize("algorithm", ["RC4-128", "AES-128", "AES-256"])
def test_every_common_encryption_algorithm_is_handled(algorithm: str):
    """AES is what raised `DependencyError` before `cryptography` was added."""
    locked = PyPdfDocumentInspector().inspect_pdf(
        an_encrypted_pdf("a-password", algorithm=algorithm)
    )
    restricted = PyPdfDocumentInspector().inspect_pdf(
        an_encrypted_pdf("", pages=3, algorithm=algorithm)
    )

    assert locked is not None and locked.is_encrypted is True
    assert restricted is not None and restricted.is_encrypted is False
    assert restricted.page_count == 3


@pytest.mark.parametrize(
    "damaged",
    [
        b"",
        b"not a pdf at all",
        b"%PDF-1.4\nthis is where it stops",
        b"%PDF-1.4\n" + b"\x00" * 200,
    ],
)
def test_an_unreadable_document_reports_nothing(damaged: bytes):
    """Refused rather than stored: LearnFlow will not keep what it cannot open."""
    assert PyPdfDocumentInspector().inspect_pdf(damaged) is None


def test_a_truncated_real_pdf_reports_nothing():
    whole = a_pdf(pages=3)

    assert PyPdfDocumentInspector().inspect_pdf(whole[: len(whole) // 3]) is None


def test_a_dependency_failure_is_a_refusal_not_a_crash(monkeypatch):
    """The regression that produced a 500 for a learner.

    `pypdf.errors.DependencyError` extends `Exception` directly rather than
    `PyPdfError`, so a tuple of named pypdf exceptions let it through. An
    AES-encrypted PDF -- which pypdf cannot even inspect without the optional
    `cryptography` package -- therefore escaped as an unhandled error, and the
    learner met "An unexpected error occurred" instead of a message naming the
    rule.
    """
    from pypdf.errors import DependencyError

    def refuses(*args, **kwargs):
        raise DependencyError("cryptography>=3.1 is required for AES algorithm")

    monkeypatch.setattr("app.infrastructure.storage.local_file_storage.PdfReader", refuses)

    assert PyPdfDocumentInspector().inspect_pdf(a_pdf()) is None


@pytest.mark.parametrize(
    "raised",
    [
        RuntimeError("something pypdf did not document"),
        MemoryError("a malicious page tree"),
        AttributeError("an internal pypdf change"),
        UnicodeDecodeError("utf-8", b"", 0, 1, "bad metadata"),
    ],
)
def test_no_parser_failure_reaches_the_caller_as_an_exception(monkeypatch, raised):
    """Whatever an untrusted file provokes, the answer is the same refusal.

    The caller treats `None` as "refuse and store nothing", so swallowing these
    cannot leave anything half-written.
    """

    def refuses(*args, **kwargs):
        raise raised

    monkeypatch.setattr("app.infrastructure.storage.local_file_storage.PdfReader", refuses)

    assert PyPdfDocumentInspector().inspect_pdf(a_pdf()) is None


def test_the_inspector_never_extracts_text():
    """The rule this feature turns on, asserted against the source itself.

    Reading a document's structure is in scope; reading its content is not, and
    this is the module where that line would be crossed first.
    """
    from pathlib import Path as SourcePath

    import app.infrastructure.storage.local_file_storage as module

    source = SourcePath(module.__file__).read_text(encoding="utf-8")

    # A *call*, not the word: the module's own docstring explains that
    # `extract_text` is deliberately never called, and that sentence is the
    # thing this test exists to keep true rather than something to forbid.
    assert ".extract_text(" not in source
    assert ".extract_images(" not in source
    assert ".images" not in source
