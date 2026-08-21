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


def test_the_root_is_created_when_it_does_not_exist(tmp_path: Path):
    """A fresh volume needs no setup step."""
    root = tmp_path / "not" / "yet" / "there"

    LocalResourceFileStorage(root=root)

    assert root.is_dir()


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


def test_the_adapter_offers_no_way_to_delete(storage: LocalResourceFileStorage):
    """The port has no removal method, and neither does this."""
    assert not hasattr(storage, "delete")
    assert not hasattr(storage, "remove")
    assert not hasattr(storage, "unlink")


# -- inspecting a PDF ---------------------------------------------------------


def test_a_real_pdf_reports_its_page_count():
    facts = PyPdfDocumentInspector().inspect_pdf(a_pdf(pages=7))

    assert facts is not None
    assert facts.page_count == 7
    assert facts.is_encrypted is False


def test_an_encrypted_pdf_is_reported_as_encrypted():
    from io import BytesIO

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("a-password")
    buffer = BytesIO()
    writer.write(buffer)

    facts = PyPdfDocumentInspector().inspect_pdf(buffer.getvalue())

    assert facts is not None
    assert facts.is_encrypted is True


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
