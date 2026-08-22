"""The rules the learning-resource use case applies (RES-001 to RES-004).

They cover what a resource must say to be storable, what it may point at, what it
may cover, and what changing one does — and, as importantly, what it does not do:
nothing here writes a stage, a plan, a plan item, or a revision, and nothing
deletes.
"""

import uuid

import pytest

from app.application.dto.resource import (
    ARCHIVED,
    MAX_TOPIC_LINKS,
    REGISTERED,
    NewResource,
    ResourceChanges,
    ResourceFilters,
    ResourceRecord,
)
from app.application.dto.resource_file import ResourceFileRecord
from app.application.dto.resource_note import ResourceNoteRecord
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_resources import (
    DuplicateTopicLinkError,
    EmptyResourceUpdateError,
    LearnerNotSetUpError,
    ManageResources,
    MissingResourceLocationError,
    MissingResourceTitleError,
    ResourceNotFoundError,
    TooManyTopicLinksError,
    UnknownResourceStatusError,
    UnknownResourceTypeError,
    UnknownTopicError,
    UnsupportedReferenceSchemeError,
)
from tests.unit.fake_learner_repository import FakeLearnerRepository, learner
from tests.unit.fake_resource_file_storage import (
    FakeResourceFileRepository,
    FakeResourceFileStorage,
)
from tests.unit.fake_resource_note_repository import FakeResourceNoteRepository
from tests.unit.fake_resource_repository import FakeResourceRepository, resource_topic


@pytest.fixture
def scheduling_topic():
    """One curriculum topic a resource can be linked to."""
    return resource_topic()


@pytest.fixture
def owner():
    """The local learner every resource in these tests belongs to."""
    return learner()


def build(owner_record, topics=(), resources=(), links=None, notes=(), files=()):
    """A use case over one learner, some topics, and any stored resources.

    The note and file stores exist for RES-005, which removes what a resource
    owns; every other operation here leaves them untouched, and most tests pass
    none.
    """
    repository = FakeResourceRepository(resources=resources, topics=topics, links=links)
    note_repository = FakeResourceNoteRepository(notes=list(notes))
    file_repository = FakeResourceFileRepository(records=list(files))
    storage = FakeResourceFileStorage()
    use_case = ManageResources(
        learners=FakeLearnerRepository((owner_record,)),
        resources=repository,
        notes=note_repository,
        files=file_repository,
        storage=storage,
    )
    return use_case, repository


def test_registering_records_the_material_and_the_topics_it_covers(owner, scheduling_topic):
    use_case, repository = build(owner, topics=[scheduling_topic])

    resource = use_case.register(
        NewResource(
            resource_type="note",
            title="Process scheduling notes",
            source_label="Blue binder, chapter 3",
            topic_ids=(scheduling_topic.id,),
        )
    )

    assert resource.title == "Process scheduling notes"
    assert resource.status == REGISTERED
    assert resource.owner_learner_id == owner.id
    assert [topic.name for topic in resource.topics] == ["CPU scheduling"]
    assert repository.links[resource.id] == (scheduling_topic.id,)


def test_a_resource_may_be_registered_with_a_label_and_no_link(owner):
    use_case, _ = build(owner)

    resource = use_case.register(
        NewResource(
            resource_type="pdf",
            title="Kanodia operating systems",
            source_label="Printed book on the shelf",
        )
    )

    assert resource.external_reference is None
    assert resource.source_label == "Printed book on the shelf"


def test_a_resource_may_be_registered_with_a_link_and_no_label(owner):
    use_case, _ = build(owner)

    resource = use_case.register(
        NewResource(
            resource_type="video_reference",
            title="Lecture series",
            external_reference="https://example.test/lectures",
        )
    )

    assert resource.external_reference == "https://example.test/lectures"
    assert resource.source_label is None


def test_a_resource_saying_neither_where_it_is_nor_what_it_is_called_is_refused(owner):
    use_case, repository = build(owner)

    with pytest.raises(MissingResourceLocationError):
        use_case.register(NewResource(resource_type="note", title="Something"))

    assert repository.resources == []


@pytest.mark.parametrize(
    "reference",
    [
        "D:\\GATE\\os-notes.pdf",
        "/home/asha/notes.pdf",
        "file:///home/asha/notes.pdf",
        "ftp://example.test/notes.pdf",
        "example.test/notes.pdf",
    ],
)
def test_a_link_that_is_not_a_web_address_is_refused(owner, reference):
    """Nothing about the learner's own machine may be stored or returned.

    docs/api/endpoints.md forbids a resource endpoint returning an absolute local
    filesystem path, so the catalogue refuses to store one in the first place.
    """
    use_case, repository = build(owner)

    with pytest.raises(UnsupportedReferenceSchemeError):
        use_case.register(
            NewResource(resource_type="pdf", title="Local notes", external_reference=reference)
        )

    assert repository.resources == []


def test_a_title_of_whitespace_alone_is_refused(owner):
    use_case, _ = build(owner)

    with pytest.raises(MissingResourceTitleError):
        use_case.register(NewResource(resource_type="note", title="   ", source_label="Shelf"))


def test_a_kind_of_material_this_build_does_not_catalogue_is_refused(owner):
    """`image` and `attachment` name uploaded files, and nothing uploads one."""
    use_case, _ = build(owner)

    with pytest.raises(UnknownResourceTypeError):
        use_case.register(
            NewResource(resource_type="attachment", title="Scan", source_label="Shelf")
        )


def test_a_topic_that_is_not_stored_is_refused(owner, scheduling_topic):
    use_case, repository = build(owner, topics=[scheduling_topic])

    with pytest.raises(UnknownTopicError):
        use_case.register(
            NewResource(
                resource_type="note",
                title="Notes",
                source_label="Shelf",
                topic_ids=(uuid.uuid4(),),
            )
        )

    assert repository.resources == []


def test_the_same_topic_named_twice_is_refused(owner, scheduling_topic):
    use_case, _ = build(owner, topics=[scheduling_topic])

    with pytest.raises(DuplicateTopicLinkError):
        use_case.register(
            NewResource(
                resource_type="note",
                title="Notes",
                source_label="Shelf",
                topic_ids=(scheduling_topic.id, scheduling_topic.id),
            )
        )


def test_more_topics_than_one_request_may_link_is_refused(owner):
    use_case, _ = build(owner)

    with pytest.raises(TooManyTopicLinksError):
        use_case.register(
            NewResource(
                resource_type="note",
                title="Notes",
                source_label="Shelf",
                topic_ids=tuple(uuid.uuid4() for _ in range(MAX_TOPIC_LINKS + 1)),
            )
        )


def test_a_resource_may_cover_a_topic_that_only_groups_subtopics(owner):
    """Deliberately unlike PRG-004, which refuses a stage on a grouping topic.

    A stage claims something about understanding a unit of work; a textbook may
    genuinely cover a whole heading. The use case asks only that the topic is
    stored.
    """
    heading = resource_topic("Operating Systems")
    use_case, _ = build(owner, topics=[heading])

    resource = use_case.register(
        NewResource(
            resource_type="pdf",
            title="Whole-subject textbook",
            source_label="Shelf",
            topic_ids=(heading.id,),
        )
    )

    assert [topic.name for topic in resource.topics] == ["Operating Systems"]


def test_registering_without_a_learner_is_refused(scheduling_topic):
    use_case = ManageResources(
        learners=FakeLearnerRepository(),
        resources=FakeResourceRepository(topics=[scheduling_topic]),
        notes=FakeResourceNoteRepository(),
        files=FakeResourceFileRepository(),
        storage=FakeResourceFileStorage(),
    )

    with pytest.raises(LearnerNotSetUpError):
        use_case.register(NewResource(resource_type="note", title="Notes", source_label="Shelf"))


def test_more_than_one_learner_is_refused_rather_than_guessed(owner):
    use_case = ManageResources(
        learners=FakeLearnerRepository((owner, learner("Ravi"))),
        resources=FakeResourceRepository(),
        notes=FakeResourceNoteRepository(),
        files=FakeResourceFileRepository(),
        storage=FakeResourceFileStorage(),
    )

    with pytest.raises(AmbiguousLocalLearnerError):
        use_case.list_resources(filters=ResourceFilters(), limit=25, offset=0)


def test_listing_before_setup_is_an_empty_page_rather_than_a_failure():
    use_case = ManageResources(
        learners=FakeLearnerRepository(),
        resources=FakeResourceRepository(),
        notes=FakeResourceNoteRepository(),
        files=FakeResourceFileRepository(),
        storage=FakeResourceFileStorage(),
    )

    page = use_case.list_resources(filters=ResourceFilters(), limit=25, offset=0)

    assert page.resources == ()
    assert page.total == 0


def test_listing_returns_the_newest_first(owner):
    use_case, _ = build(owner)
    use_case.register(NewResource(resource_type="note", title="First", source_label="Shelf"))
    use_case.register(NewResource(resource_type="note", title="Second", source_label="Shelf"))

    page = use_case.list_resources(filters=ResourceFilters(), limit=25, offset=0)

    assert [resource.title for resource in page.resources] == ["Second", "First"]


def test_listing_by_topic_finds_the_material_associated_with_it(owner, scheduling_topic):
    """FR-007's fourth acceptance criterion, answered by the API rather than a client."""
    other = resource_topic("Deadlock")
    use_case, _ = build(owner, topics=[scheduling_topic, other])
    use_case.register(
        NewResource(
            resource_type="note",
            title="Scheduling notes",
            source_label="Shelf",
            topic_ids=(scheduling_topic.id,),
        )
    )
    use_case.register(
        NewResource(
            resource_type="note",
            title="Deadlock notes",
            source_label="Shelf",
            topic_ids=(other.id,),
        )
    )

    page = use_case.list_resources(
        filters=ResourceFilters(topic_id=scheduling_topic.id), limit=25, offset=0
    )

    assert [resource.title for resource in page.resources] == ["Scheduling notes"]
    assert page.total == 1


def test_listing_by_a_topic_nothing_covers_is_an_empty_page(owner, scheduling_topic):
    use_case, _ = build(owner, topics=[scheduling_topic])
    use_case.register(NewResource(resource_type="note", title="Notes", source_label="Shelf"))

    page = use_case.list_resources(
        filters=ResourceFilters(topic_id=scheduling_topic.id), limit=25, offset=0
    )

    assert page.resources == ()


def test_an_unknown_type_or_status_filter_is_refused_rather_than_matching_nothing(owner):
    use_case, _ = build(owner)

    with pytest.raises(UnknownResourceTypeError):
        use_case.list_resources(filters=ResourceFilters(resource_type="scroll"), limit=25, offset=0)
    with pytest.raises(UnknownResourceStatusError):
        use_case.list_resources(filters=ResourceFilters(status="ready"), limit=25, offset=0)


def test_another_learners_resource_reads_as_missing(owner):
    theirs = ResourceRecord(
        id=uuid.uuid4(),
        owner_learner_id=uuid.uuid4(),
        resource_type="note",
        title="Not yours",
        source_label="Shelf",
        external_reference=None,
        status=REGISTERED,
    )
    use_case, _ = build(owner, resources=[theirs])

    with pytest.raises(ResourceNotFoundError):
        use_case.read(theirs.id)


def test_updating_replaces_the_topics_it_names(owner, scheduling_topic):
    other = resource_topic("Deadlock")
    use_case, repository = build(owner, topics=[scheduling_topic, other])
    resource = use_case.register(
        NewResource(
            resource_type="note",
            title="Notes",
            source_label="Shelf",
            topic_ids=(scheduling_topic.id,),
        )
    )

    changed = use_case.update(resource.id, ResourceChanges(topic_ids=(other.id,)))

    assert [topic.name for topic in changed.topics] == ["Deadlock"]
    assert repository.links[resource.id] == (other.id,)


def test_an_empty_topic_list_unlinks_every_topic(owner, scheduling_topic):
    use_case, repository = build(owner, topics=[scheduling_topic])
    resource = use_case.register(
        NewResource(
            resource_type="note",
            title="Notes",
            source_label="Shelf",
            topic_ids=(scheduling_topic.id,),
        )
    )

    changed = use_case.update(resource.id, ResourceChanges(topic_ids=()))

    assert changed.topics == ()
    assert resource.id not in repository.links


def test_omitting_the_topics_leaves_the_links_alone(owner, scheduling_topic):
    use_case, repository = build(owner, topics=[scheduling_topic])
    resource = use_case.register(
        NewResource(
            resource_type="note",
            title="Notes",
            source_label="Shelf",
            topic_ids=(scheduling_topic.id,),
        )
    )

    use_case.update(resource.id, ResourceChanges(title="Renamed notes"))

    assert repository.links[resource.id] == (scheduling_topic.id,)


def test_archiving_is_reversible_and_deletes_nothing(owner):
    use_case, repository = build(owner)
    resource = use_case.register(
        NewResource(resource_type="note", title="Notes", source_label="Shelf")
    )

    archived = use_case.update(resource.id, ResourceChanges(status=ARCHIVED))
    assert archived.status == ARCHIVED
    assert len(repository.resources) == 1

    restored = use_case.update(resource.id, ResourceChanges(status=REGISTERED))
    assert restored.status == REGISTERED
    assert len(repository.resources) == 1


def test_an_ingestion_status_cannot_be_asked_for(owner):
    """`ready` is documented but unwritten: nothing extracts or indexes a resource."""
    use_case, _ = build(owner)
    resource = use_case.register(
        NewResource(resource_type="note", title="Notes", source_label="Shelf")
    )

    with pytest.raises(UnknownResourceStatusError):
        use_case.update(resource.id, ResourceChanges(status="ready"))


def test_clearing_a_label_is_refused_when_it_would_leave_no_location(owner):
    use_case, _ = build(owner)
    resource = use_case.register(
        NewResource(resource_type="note", title="Notes", source_label="Shelf")
    )

    with pytest.raises(MissingResourceLocationError):
        use_case.update(resource.id, ResourceChanges(clear_source_label=True))


def test_clearing_a_label_is_allowed_when_a_link_remains(owner):
    use_case, _ = build(owner)
    resource = use_case.register(
        NewResource(
            resource_type="note",
            title="Notes",
            source_label="Shelf",
            external_reference="https://example.test/notes",
        )
    )

    changed = use_case.update(resource.id, ResourceChanges(clear_source_label=True))

    assert changed.source_label is None
    assert changed.external_reference == "https://example.test/notes"


def test_an_update_naming_nothing_is_refused(owner):
    use_case, _ = build(owner)
    resource = use_case.register(
        NewResource(resource_type="note", title="Notes", source_label="Shelf")
    )

    with pytest.raises(EmptyResourceUpdateError):
        use_case.update(resource.id, ResourceChanges())


def test_updating_one_resource_moves_no_other(owner):
    use_case, repository = build(owner)
    first = use_case.register(
        NewResource(resource_type="note", title="First", source_label="Shelf")
    )
    second = use_case.register(
        NewResource(resource_type="note", title="Second", source_label="Shelf")
    )

    use_case.update(first.id, ResourceChanges(status=ARCHIVED))

    unchanged = next(record for record in repository.resources if record.id == second.id)
    assert unchanged.status == REGISTERED
    assert unchanged.title == "Second"


def test_a_link_whose_topic_is_no_longer_stored_is_left_out_rather_than_failing(owner):
    """Losing a page because a curriculum row moved is worse than one fewer topic."""
    gone = uuid.uuid4()
    stored = ResourceRecord(
        id=uuid.uuid4(),
        owner_learner_id=owner.id,
        resource_type="note",
        title="Notes",
        source_label="Shelf",
        external_reference=None,
        status=REGISTERED,
    )
    use_case, _ = build(owner, resources=[stored], links={stored.id: [gone]})

    resource = use_case.read(stored.id)

    assert resource.topics == ()


# -- removing a whole resource (RES-005) --------------------------------------


def a_stored_file(resource_id, *, status="active"):
    """One already-stored file row belonging to a resource."""
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


def a_written_note(resource_id, *, title="Round robin", status="active"):
    """One note already kept against a resource."""
    return ResourceNoteRecord(
        id=uuid.uuid4(),
        resource_id=resource_id,
        title=title,
        body="Quantum first, then the ready queue.",
        status=status,
    )


def removable(owner_record, *, notes=(), files=()):
    """A use case over one registered resource with the owned rows supplied."""
    stored = ResourceRecord(
        id=uuid.uuid4(),
        owner_learner_id=owner_record.id,
        resource_type="pdf",
        title="Operating Systems notes",
        source_label="Blue binder",
        external_reference=None,
        status=REGISTERED,
    )
    note_records = [a_written_note(stored.id, title=title) for title in notes]
    file_records = [a_stored_file(stored.id) for _ in range(files)] if files else []
    repository = FakeResourceRepository(resources=[stored], topics=[], links=None)
    note_repository = FakeResourceNoteRepository(notes=note_records)
    file_repository = FakeResourceFileRepository(records=file_records)
    storage = FakeResourceFileStorage()
    for record in file_records:
        storage.written[record.storage_key] = b"%PDF-1.4 bytes"
    use_case = ManageResources(
        learners=FakeLearnerRepository((owner_record,)),
        resources=repository,
        notes=note_repository,
        files=file_repository,
        storage=storage,
    )
    return use_case, stored, repository, note_repository, file_repository, storage


def test_removing_a_resource_takes_everything_it_owns(owner):
    """RES-005 -- the widest destruction in LearnFlow."""
    use_case, stored, resources, notes, files, storage = removable(
        owner, notes=("First", "Second"), files=2
    )

    removed = use_case.delete(stored.id)

    assert resources.resources == []
    assert notes.notes == []
    assert files.records == []
    assert storage.written == {}
    assert removed.title == "Operating Systems notes"
    assert (removed.notes_removed, removed.files_removed, removed.bytes_unlinked) == (2, 2, 2)


def test_a_removed_resource_cannot_be_read_back(owner):
    use_case, stored, _, _, _, _ = removable(owner)

    use_case.delete(stored.id)

    with pytest.raises(ResourceNotFoundError):
        use_case.read(stored.id)


def test_removing_a_resource_with_nothing_kept_against_it_reports_nothing_lost(owner):
    use_case, stored, _, _, _, _ = removable(owner)

    removed = use_case.delete(stored.id)

    assert (removed.notes_removed, removed.files_removed, removed.bytes_unlinked) == (0, 0, 0)


def test_an_archived_resource_can_still_be_removed(owner):
    """The one place archived material is not read-only: requiring an archive
    first would turn the shelf into a deletion queue."""
    use_case, stored, resources, _, _, _ = removable(owner)
    use_case.update(stored.id, ResourceChanges(status="archived"))

    use_case.delete(stored.id)

    assert resources.resources == []


def test_removing_one_resource_leaves_another_learners_material(owner):
    stranger = learner("Ravi")
    theirs = ResourceRecord(
        id=uuid.uuid4(),
        owner_learner_id=stranger.id,
        resource_type="note",
        title="Not yours",
        source_label="Shelf",
        external_reference=None,
        status=REGISTERED,
    )
    use_case, stored, resources, _, _, _ = removable(owner)
    resources.resources.append(theirs)

    use_case.delete(stored.id)

    assert [r.title for r in resources.resources] == ["Not yours"]


def test_another_learners_resource_cannot_be_removed(owner):
    """Reported as missing rather than forbidden: existence is a disclosure."""
    stranger = learner("Ravi")
    theirs = ResourceRecord(
        id=uuid.uuid4(),
        owner_learner_id=stranger.id,
        resource_type="note",
        title="Not yours",
        source_label="Shelf",
        external_reference=None,
        status=REGISTERED,
    )
    use_case, _, resources, _, _, _ = removable(owner)
    resources.resources.append(theirs)

    with pytest.raises(ResourceNotFoundError):
        use_case.delete(theirs.id)

    assert any(r.id == theirs.id for r in resources.resources)


def test_removing_a_resource_that_is_not_there_is_refused(owner):
    use_case, _, _, _, _, _ = removable(owner)

    with pytest.raises(ResourceNotFoundError):
        use_case.delete(uuid.uuid4())


def test_the_storage_keys_are_read_before_any_row_is_deleted(owner):
    """The only workable order: once the rows are gone nothing names the bytes."""
    use_case, stored, _, _, files, storage = removable(owner, files=2)
    rows_when_unlinked = []
    unlink = storage.remove

    def watch(storage_key):
        rows_when_unlinked.append(len(files.records))
        unlink(storage_key)

    storage.remove = watch

    use_case.delete(stored.id)

    # Every unlink ran after the rows had gone, from keys captured beforehand.
    assert rows_when_unlinked == [0, 0]
    assert storage.written == {}


def test_a_failed_unlink_is_raised_so_the_whole_removal_rolls_back(owner):
    """Nothing is caught here on purpose: the exception is what undoes every row
    deletion, so a learner keeps material LearnFlow could not fully remove."""
    use_case, stored, _, _, _, storage = removable(owner, notes=("First",), files=1)

    def refuse(storage_key):
        raise OSError("read-only file system")

    storage.remove = refuse

    with pytest.raises(OSError):
        use_case.delete(stored.id)


def test_a_resource_whose_bytes_are_already_gone_is_still_removed(owner):
    """What a commit failing after an unlink, or an older volume restore, leaves.
    Asking again clears it rather than reporting a fault."""
    use_case, stored, resources, _, files, storage = removable(owner, files=2)
    storage.written.clear()

    use_case.delete(stored.id)

    assert resources.resources == []
    assert files.records == []


def test_removing_a_resource_writes_no_stage_plan_or_revision(owner):
    """A resource says where material is, never that a topic is understood."""
    use_case, stored, _, _, _, _ = removable(owner, notes=("First",), files=1)

    removed = use_case.delete(stored.id)

    assert not hasattr(removed, "learning_stage")
    assert not hasattr(removed, "plan_item_id")
