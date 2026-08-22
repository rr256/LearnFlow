"""The rules a stored PDF follows (RES-014 to RES-017).

The first group is the one that matters most: a refused upload must leave
**nothing** behind — no row and no bytes — so a rejection cannot half-succeed.

Nothing here touches a filesystem, parses a PDF, or reaches a network.
"""

import uuid

import pytest

from app.application.dto.resource import ResourceRecord
from app.application.dto.resource_file import (
    MAX_FILE_BYTES,
    MAX_FILES_PER_RESOURCE,
    MAX_PAGE_COUNT,
    ResourceFileRecord,
    ResourceFileRejection,
)
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_resource_files import (
    InvalidFileStatusError,
    LearnerNotSetUpError,
    ManageResourceFiles,
    ResourceNotWritableError,
    TooManyFilesError,
    UnknownResourceError,
    UnknownResourceFileError,
    UnsupportedFileError,
)
from tests.unit.fake_learner_repository import FakeLearnerRepository, learner
from tests.unit.fake_resource_file_storage import (
    MINIMAL_PDF,
    FakeDocumentInspector,
    FakeResourceFileRepository,
    FakeResourceFileStorage,
)
from tests.unit.fake_resource_repository import FakeResourceRepository


@pytest.fixture
def owner():
    """The local learner whose material this is."""
    return learner()


def a_resource(owner_record, *, status: str = "registered") -> ResourceRecord:
    """One piece of the learner's catalogued material."""
    return ResourceRecord(
        id=uuid.uuid4(),
        owner_learner_id=owner_record.id,
        resource_type="pdf",
        title="Operating Systems notes",
        source_label="Blue binder",
        external_reference=None,
        status=status,
    )


def build(owner_record, resource, *, files=None, inspector=None, learners=None):
    """A use case over one learner's material, with every port faked."""
    storage = FakeResourceFileStorage()
    repository = FakeResourceFileRepository(files)
    document = inspector or FakeDocumentInspector()
    use_case = ManageResourceFiles(
        learners=learners or FakeLearnerRepository((owner_record,)),
        resources=FakeResourceRepository(resources=[resource]),
        files=repository,
        storage=storage,
        inspector=document,
    )
    return use_case, storage, repository, document


def a_file(resource_id: uuid.UUID, *, status: str = "active") -> ResourceFileRecord:
    """One already-stored file."""
    return ResourceFileRecord(
        id=uuid.uuid4(),
        resource_id=resource_id,
        storage_key=f"ab/cd/{uuid.uuid4()}.pdf",
        original_filename="chapter.pdf",
        byte_size=1024,
        page_count=12,
        content_type="application/pdf",
        checksum="0" * 64,
        status=status,
    )


# -- storing a file -----------------------------------------------------------


def test_a_pdf_is_stored_with_what_describes_it(owner):
    resource = a_resource(owner)
    use_case, storage, repository, _ = build(owner, resource)

    record = use_case.store_file(
        resource_id=resource.id, filename="Chapter 3.pdf", content=MINIMAL_PDF
    )

    assert record.original_filename == "Chapter 3.pdf"
    assert record.byte_size == len(MINIMAL_PDF)
    assert record.page_count == 3
    assert record.content_type == "application/pdf"
    assert record.status == "active"
    assert len(record.checksum) == 64
    assert storage.written[record.storage_key] == MINIMAL_PDF
    assert repository.records == [record]


def test_the_stored_key_is_not_built_from_the_learners_filename(owner):
    """A browser-supplied name must not decide where anything is written."""
    resource = a_resource(owner)
    use_case, _, _, _ = build(owner, resource)

    record = use_case.store_file(
        resource_id=resource.id, filename="../../etc/passwd.pdf", content=MINIMAL_PDF
    )

    assert ".." not in record.storage_key
    assert "passwd" not in record.storage_key
    assert record.original_filename == "passwd.pdf"


def test_a_checksum_distinguishes_different_bytes(owner):
    resource = a_resource(owner)
    use_case, _, _, _ = build(owner, resource)

    first = use_case.store_file(resource_id=resource.id, filename="a.pdf", content=MINIMAL_PDF)
    second = use_case.store_file(
        resource_id=resource.id, filename="b.pdf", content=MINIMAL_PDF + b"more"
    )

    assert first.checksum != second.checksum
    # Identical uploads are two files: deduplicating would make one archive
    # action affect another record.
    assert first.storage_key != second.storage_key


# -- a refusal leaves nothing behind -----------------------------------------


@pytest.mark.parametrize(
    ("filename", "content", "rejection"),
    [
        ("notes.txt", MINIMAL_PDF, ResourceFileRejection.NOT_A_PDF),
        ("notes.pdf", b"not a pdf at all", ResourceFileRejection.NOT_A_PDF),
        ("notes.pdf", b"", ResourceFileRejection.EMPTY),
    ],
)
def test_a_refused_file_writes_no_row_and_no_bytes(owner, filename, content, rejection):
    resource = a_resource(owner)
    use_case, storage, repository, _ = build(owner, resource)

    with pytest.raises(UnsupportedFileError) as raised:
        use_case.store_file(resource_id=resource.id, filename=filename, content=content)

    assert raised.value.rejection is rejection
    assert storage.written == {}
    assert repository.records == []


def test_an_oversized_file_writes_no_row_and_no_bytes(owner):
    """Kept out of the parametrised cases above deliberately.

    A 25 MB payload in a parameter becomes part of the test's id, and pytest
    exports that id as an environment variable during teardown — which Windows
    caps at 32,767 characters. The content is built inside the test instead.
    """
    resource = a_resource(owner)
    use_case, storage, repository, _ = build(owner, resource)
    oversized = b"%PDF-" + b"x" * MAX_FILE_BYTES

    with pytest.raises(UnsupportedFileError) as raised:
        use_case.store_file(resource_id=resource.id, filename="huge.pdf", content=oversized)

    assert raised.value.rejection is ResourceFileRejection.TOO_LARGE
    assert storage.written == {}
    assert repository.records == []


def test_a_file_at_the_size_limit_is_accepted(owner):
    resource = a_resource(owner)
    use_case, _, _, _ = build(owner, resource)
    exact = b"%PDF-" + b"x" * (MAX_FILE_BYTES - 5)

    record = use_case.store_file(resource_id=resource.id, filename="big.pdf", content=exact)

    assert record.byte_size == MAX_FILE_BYTES


def test_an_unreadable_pdf_is_refused(owner):
    resource = a_resource(owner)
    use_case, storage, repository, _ = build(
        owner, resource, inspector=FakeDocumentInspector(unreadable=True)
    )

    with pytest.raises(UnsupportedFileError) as raised:
        use_case.store_file(resource_id=resource.id, filename="broken.pdf", content=MINIMAL_PDF)

    assert raised.value.rejection is ResourceFileRejection.UNREADABLE
    assert storage.written == {}
    assert repository.records == []


def test_an_encrypted_pdf_is_refused(owner):
    """LearnFlow will not store a document it can never open."""
    resource = a_resource(owner)
    use_case, storage, _, _ = build(
        owner, resource, inspector=FakeDocumentInspector(is_encrypted=True)
    )

    with pytest.raises(UnsupportedFileError) as raised:
        use_case.store_file(resource_id=resource.id, filename="locked.pdf", content=MINIMAL_PDF)

    assert raised.value.rejection is ResourceFileRejection.ENCRYPTED
    assert storage.written == {}


def test_a_pdf_with_too_many_pages_is_refused(owner):
    resource = a_resource(owner)
    use_case, storage, _, _ = build(
        owner, resource, inspector=FakeDocumentInspector(page_count=MAX_PAGE_COUNT + 1)
    )

    with pytest.raises(UnsupportedFileError) as raised:
        use_case.store_file(resource_id=resource.id, filename="huge.pdf", content=MINIMAL_PDF)

    assert raised.value.rejection is ResourceFileRejection.TOO_MANY_PAGES
    assert storage.written == {}


def test_a_pdf_at_the_page_limit_is_accepted(owner):
    resource = a_resource(owner)
    use_case, _, _, _ = build(
        owner, resource, inspector=FakeDocumentInspector(page_count=MAX_PAGE_COUNT)
    )

    record = use_case.store_file(resource_id=resource.id, filename="big.pdf", content=MINIMAL_PDF)

    assert record.page_count == MAX_PAGE_COUNT


def test_no_refusal_message_repeats_the_filename(owner):
    """A refusal names the rule, never the learner's own text."""
    resource = a_resource(owner)
    use_case, _, _, _ = build(owner, resource)
    secret = "my-private-thesis-draft.txt"

    with pytest.raises(UnsupportedFileError) as raised:
        use_case.store_file(resource_id=resource.id, filename=secret, content=MINIMAL_PDF)

    assert secret not in str(raised.value)


def test_the_size_check_happens_before_the_file_is_inspected(owner):
    """An oversized file is refused without being parsed."""
    resource = a_resource(owner)
    use_case, _, _, inspector = build(owner, resource)

    with pytest.raises(UnsupportedFileError):
        use_case.store_file(
            resource_id=resource.id,
            filename="huge.pdf",
            content=b"%PDF-" + b"x" * MAX_FILE_BYTES,
        )

    assert inspector.inspected == []


# -- bounds and ownership -----------------------------------------------------


def test_a_resource_may_not_exceed_its_file_ceiling(owner):
    resource = a_resource(owner)
    existing = [a_file(resource.id) for _ in range(MAX_FILES_PER_RESOURCE)]
    use_case, storage, _, _ = build(owner, resource, files=existing)

    with pytest.raises(TooManyFilesError):
        use_case.store_file(resource_id=resource.id, filename="one-more.pdf", content=MINIMAL_PDF)

    assert storage.written == {}


def test_archived_files_still_count_towards_the_ceiling(owner):
    """They still occupy the volume, so they still count."""
    resource = a_resource(owner)
    existing = [a_file(resource.id, status="archived") for _ in range(MAX_FILES_PER_RESOURCE)]
    use_case, _, _, _ = build(owner, resource, files=existing)

    with pytest.raises(TooManyFilesError):
        use_case.store_file(resource_id=resource.id, filename="one-more.pdf", content=MINIMAL_PDF)


def test_archived_material_accepts_no_new_file(owner):
    resource = a_resource(owner, status="archived")
    use_case, storage, _, _ = build(owner, resource)

    with pytest.raises(ResourceNotWritableError):
        use_case.store_file(resource_id=resource.id, filename="a.pdf", content=MINIMAL_PDF)

    assert storage.written == {}


def test_a_resource_belonging_to_nobody_here_is_reported_as_missing(owner):
    stranger = learner()
    resource = a_resource(stranger)
    use_case, _, _, _ = build(owner, resource)

    with pytest.raises(UnknownResourceError):
        use_case.store_file(resource_id=resource.id, filename="a.pdf", content=MINIMAL_PDF)


def test_no_learner_is_refused(owner):
    resource = a_resource(owner)
    use_case, _, _, _ = build(owner, resource, learners=FakeLearnerRepository(()))

    with pytest.raises(LearnerNotSetUpError):
        use_case.store_file(resource_id=resource.id, filename="a.pdf", content=MINIMAL_PDF)


def test_more_than_one_learner_is_refused(owner):
    resource = a_resource(owner)
    use_case, _, _, _ = build(
        owner, resource, learners=FakeLearnerRepository((learner(), learner()))
    )

    with pytest.raises(AmbiguousLocalLearnerError):
        use_case.store_file(resource_id=resource.id, filename="a.pdf", content=MINIMAL_PDF)


# -- reading back -------------------------------------------------------------


def test_files_come_back_newest_first(owner):
    resource = a_resource(owner)
    use_case, _, _, _ = build(owner, resource)
    first = use_case.store_file(resource_id=resource.id, filename="1.pdf", content=MINIMAL_PDF)
    second = use_case.store_file(resource_id=resource.id, filename="2.pdf", content=MINIMAL_PDF)

    listed = use_case.list_files(resource_id=resource.id)

    assert [record.id for record in listed] == [second.id, first.id]


def test_a_status_filter_narrows_the_list(owner):
    resource = a_resource(owner)
    use_case, _, _, _ = build(
        owner, resource, files=[a_file(resource.id), a_file(resource.id, status="archived")]
    )

    assert len(use_case.list_files(resource_id=resource.id, statuses=("active",))) == 1
    assert len(use_case.list_files(resource_id=resource.id)) == 2


def test_an_unknown_status_filter_is_refused(owner):
    resource = a_resource(owner)
    use_case, _, _, _ = build(owner, resource)

    with pytest.raises(InvalidFileStatusError):
        use_case.list_files(resource_id=resource.id, statuses=("processing",))


def test_archived_material_is_still_listable(owner):
    """Archived material is read-only, not unreadable."""
    resource = a_resource(owner, status="archived")
    use_case, _, _, _ = build(owner, resource, files=[a_file(resource.id)])

    assert len(use_case.list_files(resource_id=resource.id)) == 1


def test_a_stored_file_reads_back_byte_for_byte(owner):
    resource = a_resource(owner)
    use_case, _, _, _ = build(owner, resource)
    record = use_case.store_file(resource_id=resource.id, filename="a.pdf", content=MINIMAL_PDF)

    read = use_case.read_file(record.id)

    assert read.content == MINIMAL_PDF
    assert read.record.id == record.id


def test_an_archived_file_is_still_downloadable(owner):
    """Setting material aside hides it; it does not withhold it."""
    resource = a_resource(owner)
    use_case, _, _, _ = build(owner, resource)
    record = use_case.store_file(resource_id=resource.id, filename="a.pdf", content=MINIMAL_PDF)
    use_case.set_file_status(file_id=record.id, status="archived")

    assert use_case.read_file(record.id).content == MINIMAL_PDF


def test_a_row_whose_bytes_are_missing_is_reported_as_missing(owner):
    """A volume restored from a backup older than the database looks like this."""
    resource = a_resource(owner)
    use_case, _, _, _ = build(owner, resource, files=[a_file(resource.id)])
    orphan = use_case.list_files(resource_id=resource.id)[0]

    with pytest.raises(UnknownResourceFileError):
        use_case.read_file(orphan.id)


def test_another_learners_file_is_reported_as_missing(owner):
    stranger = learner()
    resource = a_resource(stranger)
    use_case, _, _, _ = build(owner, resource, files=[a_file(resource.id)])
    theirs = use_case._files.records[0]

    with pytest.raises(UnknownResourceFileError):
        use_case.read_file(theirs.id)


# -- setting aside ------------------------------------------------------------


def test_a_file_moves_between_statuses_in_both_directions(owner):
    resource = a_resource(owner)
    use_case, storage, _, _ = build(owner, resource)
    record = use_case.store_file(resource_id=resource.id, filename="a.pdf", content=MINIMAL_PDF)

    aside = use_case.set_file_status(file_id=record.id, status="archived")
    back = use_case.set_file_status(file_id=record.id, status="active")

    assert aside.status == "archived"
    assert back.status == "active"
    # The bytes never moved.
    assert storage.written[record.storage_key] == MINIMAL_PDF


def test_archiving_removes_no_bytes(owner):
    resource = a_resource(owner)
    use_case, storage, _, _ = build(owner, resource)
    record = use_case.store_file(resource_id=resource.id, filename="a.pdf", content=MINIMAL_PDF)

    use_case.set_file_status(file_id=record.id, status="archived")

    assert list(storage.written) == [record.storage_key]


def test_an_unknown_status_is_refused(owner):
    resource = a_resource(owner)
    use_case, _, _, _ = build(owner, resource, files=[a_file(resource.id)])
    stored = use_case.list_files(resource_id=resource.id)[0]

    with pytest.raises(InvalidFileStatusError):
        use_case.set_file_status(file_id=stored.id, status="deleted")


def test_a_file_on_archived_material_may_not_be_moved(owner):
    resource = a_resource(owner, status="archived")
    use_case, _, _, _ = build(owner, resource, files=[a_file(resource.id)])
    stored = use_case.list_files(resource_id=resource.id)[0]

    with pytest.raises(ResourceNotWritableError):
        use_case.set_file_status(file_id=stored.id, status="archived")


# -- what does not happen -----------------------------------------------------


def test_the_use_case_binds_no_provider(owner):
    """Five collaborators, none of which can reach a network."""
    resource = a_resource(owner)
    use_case, _, _, _ = build(owner, resource)

    assert set(vars(use_case)) == {
        "_learners",
        "_resources",
        "_files",
        "_storage",
        "_inspector",
    }


# -- removing a stored file --------------------------------------------------


def test_removing_a_file_deletes_both_the_row_and_the_bytes(owner):
    """RES-018 — the narrow exception to "nothing is destroyed"."""
    resource = a_resource(owner)
    use_case, storage, repository, _ = build(owner, resource)
    record = use_case.store_file(resource_id=resource.id, filename="wrong.pdf", content=MINIMAL_PDF)

    use_case.delete_file(record.id)

    assert repository.records == []
    assert storage.written == {}


def test_removing_one_file_leaves_the_others_untouched(owner):
    resource = a_resource(owner)
    use_case, storage, repository, _ = build(owner, resource)
    keep = use_case.store_file(resource_id=resource.id, filename="keep.pdf", content=MINIMAL_PDF)
    drop = use_case.store_file(resource_id=resource.id, filename="drop.pdf", content=MINIMAL_PDF)

    use_case.delete_file(drop.id)

    assert [r.id for r in repository.records] == [keep.id]
    assert list(storage.written) == [keep.storage_key]


def test_a_removed_file_frees_a_place_against_the_ceiling(owner):
    resource = a_resource(owner)
    existing = [a_file(resource.id) for _ in range(MAX_FILES_PER_RESOURCE)]
    use_case, _, _, _ = build(owner, resource, files=existing)

    use_case.delete_file(existing[0].id)
    stored = use_case.store_file(resource_id=resource.id, filename="new.pdf", content=MINIMAL_PDF)

    assert stored.original_filename == "new.pdf"


def test_a_removed_file_cannot_be_read_back(owner):
    resource = a_resource(owner)
    use_case, _, _, _ = build(owner, resource)
    record = use_case.store_file(resource_id=resource.id, filename="a.pdf", content=MINIMAL_PDF)

    use_case.delete_file(record.id)

    with pytest.raises(UnknownResourceFileError):
        use_case.read_file(record.id)


def test_another_learners_file_cannot_be_removed(owner):
    stranger = learner()
    resource = a_resource(stranger)
    use_case, _, repository, _ = build(owner, resource, files=[a_file(resource.id)])
    theirs = repository.records[0]

    with pytest.raises(UnknownResourceFileError):
        use_case.delete_file(theirs.id)

    assert len(repository.records) == 1


def test_a_file_on_archived_material_cannot_be_removed(owner):
    """Archived material is read-only everywhere, and deletion is no exception."""
    resource = a_resource(owner, status="archived")
    use_case, _, repository, _ = build(owner, resource, files=[a_file(resource.id)])

    with pytest.raises(ResourceNotWritableError):
        use_case.delete_file(repository.records[0].id)

    assert len(repository.records) == 1


def test_an_archived_file_can_still_be_removed(owner):
    """Setting aside and removing are different answers to the same mistake."""
    resource = a_resource(owner)
    use_case, storage, repository, _ = build(owner, resource)
    record = use_case.store_file(resource_id=resource.id, filename="a.pdf", content=MINIMAL_PDF)
    use_case.set_file_status(file_id=record.id, status="archived")

    use_case.delete_file(record.id)

    assert repository.records == []
    assert storage.written == {}


def test_removing_a_file_that_is_not_there_is_refused(owner):
    resource = a_resource(owner)
    use_case, _, _, _ = build(owner, resource)

    with pytest.raises(UnknownResourceFileError):
        use_case.delete_file(uuid.uuid4())


def test_the_row_is_removed_before_the_bytes_are_unlinked(owner):
    """The order is what makes a failed unlink safe: the row deletion is still
    uncommitted when it runs, so raising undoes it."""
    resource = a_resource(owner)
    use_case, storage, repository, _ = build(owner, resource)
    record = use_case.store_file(resource_id=resource.id, filename="a.pdf", content=MINIMAL_PDF)
    rows_when_unlinked: list[int] = []
    unlink = storage.remove

    def watch(storage_key: str) -> None:
        rows_when_unlinked.append(len(repository.records))
        unlink(storage_key)

    storage.remove = watch

    use_case.delete_file(record.id)

    assert rows_when_unlinked == [0]


def test_a_failed_unlink_is_raised_rather_than_swallowed(owner):
    """Nothing catches it here on purpose. The exception is what rolls the row
    deletion back, so a learner keeps a file LearnFlow could not delete."""
    resource = a_resource(owner)
    use_case, storage, _, _ = build(owner, resource)
    record = use_case.store_file(resource_id=resource.id, filename="a.pdf", content=MINIMAL_PDF)

    def refuse(storage_key: str) -> None:
        raise OSError("read-only file system")

    storage.remove = refuse

    with pytest.raises(OSError):
        use_case.delete_file(record.id)


def test_a_file_whose_bytes_are_already_gone_is_still_removed(owner):
    """The state a commit failing after an unlink would leave behind, and the
    state a volume restored from an older backup produces. Asking again clears
    it rather than reporting a fault."""
    resource = a_resource(owner)
    use_case, storage, repository, _ = build(owner, resource)
    record = use_case.store_file(resource_id=resource.id, filename="a.pdf", content=MINIMAL_PDF)
    storage.written.clear()

    use_case.delete_file(record.id)

    assert repository.records == []


def test_nothing_extracts_text_from_a_stored_file(owner):
    """The inspector is handed bytes and asked for structure, never content."""
    resource = a_resource(owner)
    use_case, _, _, inspector = build(owner, resource)

    record = use_case.store_file(resource_id=resource.id, filename="a.pdf", content=MINIMAL_PDF)

    assert inspector.inspected == [MINIMAL_PDF]
    assert not hasattr(record, "text")
    assert not hasattr(record, "extracted_text")
