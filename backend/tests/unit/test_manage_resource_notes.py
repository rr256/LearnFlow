"""The rules the resource-note use case applies (RES-009 to RES-012).

They cover what a note must say to be storable, how much it may hold, whose
material it may be written against, and what changing one does — and, as
importantly, what it does not do. Nothing here uploads, fetches, extracts,
chunks, embeds, indexes, searches, or ranks; nothing writes a resource, a stage,
a plan, a plan item, a revision, or a quiz; and nothing deletes.
"""

import uuid

import pytest

from app.application.dto.resource import ARCHIVED as RESOURCE_ARCHIVED
from app.application.dto.resource import REGISTERED, ResourceRecord
from app.application.dto.resource_note import (
    ACTIVE,
    ARCHIVED,
    MAX_NOTE_BODY_LENGTH,
    MAX_NOTE_TITLE_LENGTH,
    MAX_NOTES_PER_RESOURCE,
    NewResourceNote,
    ResourceNoteChanges,
    ResourceNoteFilters,
    ResourceNoteRecord,
)
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_resource_notes import (
    ArchivedResourceError,
    EmptyNoteUpdateError,
    ManageResourceNotes,
    MissingNoteBodyError,
    MissingNoteTitleError,
    NoteTitleTooLongError,
    NoteTooLongError,
    ResourceNoteNotFoundError,
    ResourceNotFoundError,
    TooManyNotesError,
    UnknownNoteStatusError,
)
from tests.unit.fake_learner_repository import FakeLearnerRepository, learner
from tests.unit.fake_resource_note_repository import FakeResourceNoteRepository
from tests.unit.fake_resource_repository import FakeResourceRepository


@pytest.fixture
def owner():
    """The local learner every resource in these tests belongs to."""
    return learner()


def a_resource(owner_record, *, status: str = REGISTERED) -> ResourceRecord:
    """One piece of the learner's catalogued material."""
    return ResourceRecord(
        id=uuid.uuid4(),
        owner_learner_id=owner_record.id,
        resource_type="note",
        title="Process scheduling notes",
        source_label="Blue binder, chapter 3",
        external_reference=None,
        status=status,
    )


def build(owner_record, resources=(), notes=()):
    """A use case over one learner, their material, and any notes on it."""
    note_repository = FakeResourceNoteRepository(notes)
    use_case = ManageResourceNotes(
        learners=FakeLearnerRepository((owner_record,)),
        resources=FakeResourceRepository(resources=resources),
        notes=note_repository,
    )
    return use_case, note_repository


def a_note(
    resource_id: uuid.UUID,
    *,
    title: str = "Deadlock conditions",
    body: str = "Text.",
    status: str = ACTIVE,
) -> ResourceNoteRecord:
    """One note already written against a resource."""
    return ResourceNoteRecord(
        id=uuid.uuid4(), resource_id=resource_id, title=title, body=body, status=status
    )


def test_a_note_is_kept_against_the_material_it_was_written_about(owner):
    resource = a_resource(owner)
    use_case, repository = build(owner, resources=[resource])

    note = use_case.add(
        resource.id,
        NewResourceNote(title="Deadlock conditions", body="Mutual exclusion, hold and wait."),
    )

    assert note.title == "Deadlock conditions"
    assert note.body == "Mutual exclusion, hold and wait."
    assert note.resource_id == resource.id
    assert note.status == ACTIVE
    assert len(repository.notes) == 1


def test_a_learners_line_breaks_and_spacing_survive_exactly(owner):
    """The one thing this feature promises: what you wrote is what you read back.

    Surrounding whitespace goes; nothing inside the note is touched. Rewriting a
    learner's own text would change what they wrote, and docs/rag/ingestion.md's
    normalisation step belongs to a pipeline reading files rather than to this.
    """
    resource = a_resource(owner)
    use_case, _ = build(owner, resources=[resource])
    pasted = "\n  Step one:\n\n      indented code\n\n  Step two.\n  "

    note = use_case.add(resource.id, NewResourceNote(title="Steps", body=pasted))

    assert note.body == "Step one:\n\n      indented code\n\n  Step two."


def test_line_terminators_are_canonicalised_however_the_form_was_posted(owner):
    """A form posted without JavaScript delivers CRLF; a hydrated one delivers LF.

    The HTML form-data encoding algorithm normalises newlines, so the same note
    would otherwise be stored two different ways depending on whether a browser
    ran JavaScript. Found by the production standalone run with JavaScript
    disabled, which is the only check that submits a real multipart form.
    """
    resource = a_resource(owner)
    use_case, _ = build(owner, resources=[resource])

    without_js = use_case.add(
        resource.id,
        NewResourceNote(title="Posted", body="Line one.\r\n\r\n\tTabbed.\r\nEnd."),
    )
    with_js = use_case.add(
        resource.id, NewResourceNote(title="Sent", body="Line one.\n\n\tTabbed.\nEnd.")
    )

    assert without_js.body == with_js.body == "Line one.\n\n\tTabbed.\nEnd."
    assert "\r" not in without_js.body


def test_a_lone_carriage_return_is_canonicalised_too(owner):
    resource = a_resource(owner)
    use_case, _ = build(owner, resources=[resource])

    note = use_case.add(resource.id, NewResourceNote(title="Old Mac", body="One.\rTwo."))

    assert note.body == "One.\nTwo."


def test_canonicalising_terminators_changes_nothing_else(owner):
    """It is not ingestion's normalisation step: no visible character moves."""
    resource = a_resource(owner)
    use_case, _ = build(owner, resources=[resource])
    pasted = "  Two  spaces   inside.\n\n\n\nFour blank lines above.\t\tTwo tabs."

    note = use_case.add(resource.id, NewResourceNote(title="Untouched", body=pasted))

    assert note.body == pasted.strip()


def test_a_correction_canonicalises_terminators_as_a_first_write_does(owner):
    resource = a_resource(owner)
    note = a_note(resource.id)
    use_case, _ = build(owner, resources=[resource], notes=[note])

    corrected = use_case.update(note.id, ResourceNoteChanges(body="A.\r\nB."))

    assert corrected.body == "A.\nB."


def test_a_note_is_written_active_and_no_status_is_accepted_at_creation(owner):
    resource = a_resource(owner)
    use_case, _ = build(owner, resources=[resource])

    note = use_case.add(resource.id, NewResourceNote(title="A title", body="Some text."))

    assert note.status == ACTIVE
    assert not hasattr(NewResourceNote("t", "b"), "status")


def test_a_note_needs_some_text_in_it(owner):
    resource = a_resource(owner)
    use_case, _ = build(owner, resources=[resource])

    with pytest.raises(MissingNoteBodyError):
        use_case.add(resource.id, NewResourceNote(title="A title", body="   \n  "))


def test_a_note_needs_a_title(owner):
    resource = a_resource(owner)
    use_case, _ = build(owner, resources=[resource])

    with pytest.raises(MissingNoteTitleError):
        use_case.add(resource.id, NewResourceNote(title="  ", body="Some text."))


def test_a_note_longer_than_the_bound_is_refused_without_quoting_it(owner):
    """The refusal names the rule and never echoes the learner's own text.

    docs/api/conventions.md forbids echoing any rejected value; this is the field
    where it matters most, because the value is the learner's study material.
    """
    resource = a_resource(owner)
    use_case, _ = build(owner, resources=[resource])
    secret = "s3cret-study-note " * 2000
    assert len(secret) > MAX_NOTE_BODY_LENGTH

    with pytest.raises(NoteTooLongError) as raised:
        use_case.add(resource.id, NewResourceNote(title="A title", body=secret))

    assert "s3cret-study-note" not in str(raised.value)
    assert str(MAX_NOTE_BODY_LENGTH) in str(raised.value)


def test_a_note_exactly_at_the_bound_is_accepted(owner):
    resource = a_resource(owner)
    use_case, _ = build(owner, resources=[resource])

    note = use_case.add(
        resource.id, NewResourceNote(title="A title", body="x" * MAX_NOTE_BODY_LENGTH)
    )

    assert len(note.body) == MAX_NOTE_BODY_LENGTH


def test_a_title_longer_than_a_label_is_refused(owner):
    resource = a_resource(owner)
    use_case, _ = build(owner, resources=[resource])

    with pytest.raises(NoteTitleTooLongError):
        use_case.add(
            resource.id,
            NewResourceNote(title="t" * (MAX_NOTE_TITLE_LENGTH + 1), body="Some text."),
        )


def test_one_resource_cannot_hold_more_notes_than_the_bound(owner):
    """A bound on one note is no bound at all without a bound on their number."""
    resource = a_resource(owner)
    stored = [a_note(resource.id) for _ in range(MAX_NOTES_PER_RESOURCE)]
    use_case, _ = build(owner, resources=[resource], notes=stored)

    with pytest.raises(TooManyNotesError):
        use_case.add(resource.id, NewResourceNote(title="One more", body="Some text."))


def test_notes_put_aside_still_count_towards_the_bound(owner):
    """Otherwise the bound could be stepped around by archiving."""
    resource = a_resource(owner)
    stored = [a_note(resource.id, status=ARCHIVED) for _ in range(MAX_NOTES_PER_RESOURCE)]
    use_case, _ = build(owner, resources=[resource], notes=stored)

    with pytest.raises(TooManyNotesError):
        use_case.add(resource.id, NewResourceNote(title="One more", body="Some text."))


def test_material_that_is_not_the_learners_is_reported_as_missing(owner):
    somebody_elses = ResourceRecord(
        id=uuid.uuid4(),
        owner_learner_id=uuid.uuid4(),
        resource_type="note",
        title="Not yours",
        source_label="Elsewhere",
        external_reference=None,
        status=REGISTERED,
    )
    use_case, _ = build(owner, resources=[somebody_elses])

    with pytest.raises(ResourceNotFoundError):
        use_case.add(somebody_elses.id, NewResourceNote(title="A title", body="Some text."))


def test_no_note_can_be_written_against_material_that_is_put_aside(owner):
    """Archived material is read-only, as RES-004 and ADR-035 both establish."""
    resource = a_resource(owner, status=RESOURCE_ARCHIVED)
    use_case, _ = build(owner, resources=[resource])

    with pytest.raises(ArchivedResourceError):
        use_case.add(resource.id, NewResourceNote(title="A title", body="Some text."))


def test_a_note_on_material_that_is_put_aside_cannot_be_changed_either(owner):
    resource = a_resource(owner, status=RESOURCE_ARCHIVED)
    note = a_note(resource.id)
    use_case, _ = build(owner, resources=[resource], notes=[note])

    with pytest.raises(ArchivedResourceError):
        use_case.update(note.id, ResourceNoteChanges(title="A better title"))


def test_the_notes_of_material_put_aside_are_still_readable(owner):
    """Putting material aside stops it being written to; it hides nothing."""
    resource = a_resource(owner, status=RESOURCE_ARCHIVED)
    note = a_note(resource.id, body="Still here.")
    use_case, _ = build(owner, resources=[resource], notes=[note])

    assert use_case.read(note.id).body == "Still here."
    page = use_case.list_notes(resource.id, filters=ResourceNoteFilters(), limit=10, offset=0)
    assert [stored.id for stored in page.notes] == [note.id]


def test_notes_are_listed_newest_first(owner):
    resource = a_resource(owner)
    first = a_note(resource.id, title="First")
    second = a_note(resource.id, title="Second")
    use_case, _ = build(owner, resources=[resource], notes=[first, second])

    page = use_case.list_notes(resource.id, filters=ResourceNoteFilters(), limit=10, offset=0)

    assert [note.title for note in page.notes] == ["Second", "First"]
    assert page.total == 2


def test_no_status_is_assumed_when_notes_are_listed(owner):
    """A caller asks for what it wants, as RES-002, PLN-002, and REV-001 require."""
    resource = a_resource(owner)
    kept = a_note(resource.id, title="Kept")
    aside = a_note(resource.id, title="Aside", status=ARCHIVED)
    use_case, _ = build(owner, resources=[resource], notes=[kept, aside])

    unfiltered = use_case.list_notes(resource.id, filters=ResourceNoteFilters(), limit=10, offset=0)
    active_only = use_case.list_notes(
        resource.id, filters=ResourceNoteFilters(status=ACTIVE), limit=10, offset=0
    )

    assert {note.title for note in unfiltered.notes} == {"Kept", "Aside"}
    assert [note.title for note in active_only.notes] == ["Kept"]


def test_another_resources_notes_are_not_listed(owner):
    mine = a_resource(owner)
    other = a_resource(owner)
    use_case, _ = build(
        owner,
        resources=[mine, other],
        notes=[a_note(mine.id, title="Mine"), a_note(other.id, title="Other")],
    )

    page = use_case.list_notes(mine.id, filters=ResourceNoteFilters(), limit=10, offset=0)

    assert [note.title for note in page.notes] == ["Mine"]


def test_a_status_filter_outside_the_two_is_refused(owner):
    resource = a_resource(owner)
    use_case, _ = build(owner, resources=[resource])

    with pytest.raises(UnknownNoteStatusError):
        use_case.list_notes(
            resource.id, filters=ResourceNoteFilters(status="indexed"), limit=10, offset=0
        )


def test_a_note_is_corrected_in_place_however_often_the_learner_likes(owner):
    """Unlike a practice question, whose wording ADR-035 fixes once a quiz asks it.

    Nothing reads a note, so no stored record can be made to disagree with a
    correction.
    """
    resource = a_resource(owner)
    note = a_note(resource.id, title="Rough", body="First draft.")
    use_case, repository = build(owner, resources=[resource], notes=[note])

    once = use_case.update(note.id, ResourceNoteChanges(body="Second draft."))
    twice = use_case.update(note.id, ResourceNoteChanges(body="Third draft."))

    assert once.id == twice.id == note.id
    assert twice.body == "Third draft."
    assert twice.title == "Rough"
    assert len(repository.notes) == 1


def test_putting_a_note_aside_is_reversible_and_destroys_nothing(owner):
    resource = a_resource(owner)
    note = a_note(resource.id, body="Worth keeping.")
    use_case, repository = build(owner, resources=[resource], notes=[note])

    aside = use_case.update(note.id, ResourceNoteChanges(status=ARCHIVED))
    back = use_case.update(note.id, ResourceNoteChanges(status=ACTIVE))

    assert aside.status == ARCHIVED
    assert back.status == ACTIVE
    assert back.body == "Worth keeping."
    assert len(repository.notes) == 1


def test_a_note_can_be_removed_permanently(owner):
    """RES-019 — the narrow exception to "nothing is destroyed"."""
    resource = a_resource(owner)
    note = a_note(resource.id, body="Added by mistake.")
    use_case, repository = build(owner, resources=[resource], notes=[note])

    use_case.delete(note.id)

    assert repository.notes == []


def test_removing_a_note_leaves_the_others(owner):
    resource = a_resource(owner)
    keep, remove = a_note(resource.id, title="Keep"), a_note(resource.id, title="Remove")
    use_case, repository = build(owner, resources=[resource], notes=[keep, remove])

    use_case.delete(remove.id)

    assert [note.title for note in repository.notes] == ["Keep"]


def test_a_removed_note_cannot_be_read_back(owner):
    resource = a_resource(owner)
    note = a_note(resource.id)
    use_case, _ = build(owner, resources=[resource], notes=[note])

    use_case.delete(note.id)

    with pytest.raises(ResourceNoteNotFoundError):
        use_case.read(note.id)


def test_another_learners_note_cannot_be_removed(owner):
    """Reported as missing, not as forbidden: existence is itself a disclosure."""
    stranger = learner()
    resource = a_resource(stranger)
    note = a_note(resource.id)
    use_case, repository = build(owner, resources=[resource], notes=[note])

    with pytest.raises(ResourceNoteNotFoundError):
        use_case.delete(note.id)

    assert len(repository.notes) == 1


def test_a_note_on_archived_material_cannot_be_removed(owner):
    """Archived material is read-only everywhere, and deletion is no exception."""
    resource = a_resource(owner, status="archived")
    note = a_note(resource.id)
    use_case, repository = build(owner, resources=[resource], notes=[note])

    with pytest.raises(ArchivedResourceError):
        use_case.delete(note.id)

    assert len(repository.notes) == 1


def test_removing_a_note_that_is_not_there_is_refused_rather_than_ignored(owner):
    """The use case still checks ownership before the repository is asked."""
    resource = a_resource(owner)
    use_case, _ = build(owner, resources=[resource], notes=[])

    with pytest.raises(ResourceNoteNotFoundError):
        use_case.delete(uuid.uuid4())


def test_an_update_naming_nothing_is_refused(owner):
    resource = a_resource(owner)
    note = a_note(resource.id)
    use_case, _ = build(owner, resources=[resource], notes=[note])

    with pytest.raises(EmptyNoteUpdateError):
        use_case.update(note.id, ResourceNoteChanges())


def test_an_update_to_an_unknown_status_is_refused(owner):
    resource = a_resource(owner)
    note = a_note(resource.id)
    use_case, _ = build(owner, resources=[resource], notes=[note])

    with pytest.raises(UnknownNoteStatusError):
        use_case.update(note.id, ResourceNoteChanges(status="embedded"))


def test_a_correction_that_empties_a_note_is_refused(owner):
    resource = a_resource(owner)
    note = a_note(resource.id, body="Worth keeping.")
    use_case, repository = build(owner, resources=[resource], notes=[note])

    with pytest.raises(MissingNoteBodyError):
        use_case.update(note.id, ResourceNoteChanges(body="   "))
    assert repository.notes[0].body == "Worth keeping."


def test_a_note_belonging_to_another_learner_is_reported_as_missing(owner):
    """Reported as missing rather than forbidden: the rule every owned read follows."""
    somebody_elses = ResourceRecord(
        id=uuid.uuid4(),
        owner_learner_id=uuid.uuid4(),
        resource_type="note",
        title="Not yours",
        source_label="Elsewhere",
        external_reference=None,
        status=REGISTERED,
    )
    note = a_note(somebody_elses.id)
    use_case, _ = build(owner, resources=[somebody_elses], notes=[note])

    with pytest.raises(ResourceNoteNotFoundError):
        use_case.read(note.id)
    with pytest.raises(ResourceNoteNotFoundError):
        use_case.update(note.id, ResourceNoteChanges(title="Mine now"))


def test_an_unknown_note_is_reported_as_missing(owner):
    use_case, _ = build(owner)

    with pytest.raises(ResourceNoteNotFoundError):
        use_case.read(uuid.uuid4())


def test_more_than_one_stored_learner_is_refused(owner):
    resource = a_resource(owner)
    use_case = ManageResourceNotes(
        learners=FakeLearnerRepository((owner, learner())),
        resources=FakeResourceRepository(resources=[resource]),
        notes=FakeResourceNoteRepository(),
    )

    with pytest.raises(AmbiguousLocalLearnerError):
        use_case.add(resource.id, NewResourceNote(title="A title", body="Some text."))


def test_the_use_case_binds_no_provider_a_note_could_leave_through(owner):
    """NFR-001, asserted rather than promised.

    A learner's note has no path out of this process: the use case holds three
    repositories and nothing else. Adding an AI, embedding, or retrieval provider
    to this constructor is the visible decision that would begin retrieval, and
    this test is what makes it visible.
    """
    resource = a_resource(owner)
    use_case, _ = build(owner, resources=[resource])

    bound = {name for name in vars(use_case) if not name.startswith("__")}

    assert bound == {"_learners", "_resources", "_notes"}


def test_writing_a_note_moves_nothing_else(owner):
    """No resource, no topic link, no stage, no plan, no revision, no quiz."""
    resource = a_resource(owner)
    note_repository = FakeResourceNoteRepository()
    resource_repository = FakeResourceRepository(resources=[resource])
    use_case = ManageResourceNotes(
        learners=FakeLearnerRepository((owner,)),
        resources=resource_repository,
        notes=note_repository,
    )

    use_case.add(resource.id, NewResourceNote(title="A title", body="Some text."))

    assert resource_repository.resources == [resource]
    assert resource_repository.links == {}
