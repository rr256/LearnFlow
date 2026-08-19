"""The rules topic-note retrieval applies (RES-013).

They cover which notes are eligible, what an empty answer says and why, and what
the search does not do. Nothing here asks a model anything, writes anything, or
reports a figure about the learner.
"""

import uuid

import pytest

from app.application.dto.note_retrieval import (
    MAX_PASSAGE_WORDS,
    MAX_PASSAGES,
    TopicNoteSearchOutcome,
)
from app.application.dto.resource import ResourceRecord
from app.application.dto.resource_note import ResourceNoteRecord
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.retrieve_topic_notes import (
    LearnerNotSetUpError,
    RetrieveTopicNotes,
    UnknownTopicError,
    extract_passage,
    search_terms_for,
)
from tests.unit.fake_learner_repository import FakeLearnerRepository, learner
from tests.unit.fake_note_search_repository import FakeNoteSearchRepository
from tests.unit.fake_resource_repository import FakeResourceRepository, resource_topic


@pytest.fixture
def owner():
    """The local learner whose notes are searched."""
    return learner()


@pytest.fixture
def scheduling():
    """The topic every search in these tests asks about."""
    return resource_topic(name="CPU scheduling", subject_name="Operating Systems")


def a_resource(owner_record, *, status: str = "registered") -> ResourceRecord:
    """One piece of the learner's catalogued material."""
    return ResourceRecord(
        id=uuid.uuid4(),
        owner_learner_id=owner_record.id,
        resource_type="note",
        title="Operating Systems notes",
        source_label="Blue binder",
        external_reference=None,
        status=status,
    )


def a_note(
    resource_id: uuid.UUID,
    *,
    title: str = "Scheduling",
    body: str = "Round robin scheduling.",
    status: str = "active",
) -> ResourceNoteRecord:
    """One note on that material."""
    return ResourceNoteRecord(
        id=uuid.uuid4(), resource_id=resource_id, title=title, body=body, status=status
    )


def build(owner_record, topic, *, resources=(), notes=(), links=None):
    """A use case over one learner, their material, its notes, and the topic links."""
    search = FakeNoteSearchRepository(
        resources=resources, notes=notes, topics=[topic], links=links or {}
    )
    use_case = RetrieveTopicNotes(
        learners=FakeLearnerRepository((owner_record,)),
        resources=FakeResourceRepository(topics=[topic]),
        notes=search,
    )
    return use_case, search


# -- what comes back ----------------------------------------------------------


def test_a_matching_passage_comes_back_with_where_it_came_from(owner, scheduling):
    resource = a_resource(owner)
    note = a_note(resource.id, body="Round robin scheduling gives each process a quantum.")
    use_case, _ = build(
        owner, scheduling, resources=[resource], notes=[note], links={resource.id: [scheduling.id]}
    )

    result = use_case.search(scheduling.id)

    assert result.outcome is TopicNoteSearchOutcome.FOUND
    assert len(result.passages) == 1
    passage = result.passages[0]
    assert passage.note_id == note.id
    assert passage.resource_title == "Operating Systems notes"
    assert passage.resource_type == "note"
    assert passage.topic_name == "CPU scheduling"
    assert passage.subject_name == "Operating Systems"
    assert "Round robin scheduling" in passage.passage


def test_the_result_names_the_topic_that_was_asked_about(owner, scheduling):
    resource = a_resource(owner)
    use_case, _ = build(
        owner,
        scheduling,
        resources=[resource],
        notes=[a_note(resource.id)],
        links={resource.id: [scheduling.id]},
    )

    result = use_case.search(scheduling.id)

    assert result.topic_id == scheduling.id
    assert result.topic_name == "CPU scheduling"
    assert result.subject_name == "Operating Systems"


def test_no_relevance_figure_reaches_the_result(owner, scheduling):
    """Relevance decides the order and nothing else.

    A number beside a learner's own writing reads as a mark on it, which is the
    line docs/domain/terminology.md draws.
    """
    resource = a_resource(owner)
    use_case, _ = build(
        owner,
        scheduling,
        resources=[resource],
        notes=[a_note(resource.id)],
        links={resource.id: [scheduling.id]},
    )

    passage = use_case.search(scheduling.id).passages[0]

    fields = set(passage.__slots__)
    for forbidden in ("rank", "score", "relevance", "similarity", "confidence", "match_count"):
        assert forbidden not in fields


def test_more_relevant_passages_come_first(owner, scheduling):
    resource = a_resource(owner)
    weak = a_note(resource.id, title="Aside", body="Scheduling is mentioned once.")
    strong = a_note(resource.id, title="CPU", body="CPU scheduling: the CPU picks a process.")
    use_case, _ = build(
        owner,
        scheduling,
        resources=[resource],
        notes=[weak, strong],
        links={resource.id: [scheduling.id]},
    )

    result = use_case.search(scheduling.id)

    assert [passage.note_id for passage in result.passages] == [strong.id, weak.id]


def test_at_most_one_page_of_passages_is_returned(owner, scheduling):
    resource = a_resource(owner)
    notes = [a_note(resource.id) for _ in range(MAX_PASSAGES + 5)]
    use_case, search = build(
        owner, scheduling, resources=[resource], notes=notes, links={resource.id: [scheduling.id]}
    )

    result = use_case.search(scheduling.id)

    assert len(result.passages) == MAX_PASSAGES
    assert search.searches[0][1]  # the terms were supplied rather than left blank


# -- eligibility --------------------------------------------------------------


def test_a_note_the_learner_put_aside_is_not_searched(owner, scheduling):
    resource = a_resource(owner)
    use_case, _ = build(
        owner,
        scheduling,
        resources=[resource],
        notes=[a_note(resource.id, status="archived")],
        links={resource.id: [scheduling.id]},
    )

    assert use_case.search(scheduling.id).outcome is TopicNoteSearchOutcome.NO_ACTIVE_NOTES


def test_a_note_on_material_put_aside_is_not_searched(owner, scheduling):
    """Archiving a resource means one thing on every screen, including this one."""
    resource = a_resource(owner, status="archived")
    use_case, _ = build(
        owner,
        scheduling,
        resources=[resource],
        notes=[a_note(resource.id)],
        links={resource.id: [scheduling.id]},
    )

    assert use_case.search(scheduling.id).outcome is TopicNoteSearchOutcome.NO_LINKED_MATERIAL


def test_material_not_linked_to_the_topic_is_not_searched(owner, scheduling):
    resource = a_resource(owner)
    use_case, _ = build(
        owner, scheduling, resources=[resource], notes=[a_note(resource.id)], links={}
    )

    assert use_case.search(scheduling.id).outcome is TopicNoteSearchOutcome.NO_LINKED_MATERIAL


def test_another_learners_material_is_never_searched(owner, scheduling):
    somebody_elses = ResourceRecord(
        id=uuid.uuid4(),
        owner_learner_id=uuid.uuid4(),
        resource_type="note",
        title="Not yours",
        source_label="Elsewhere",
        external_reference=None,
        status="registered",
    )
    use_case, _ = build(
        owner,
        scheduling,
        resources=[somebody_elses],
        notes=[a_note(somebody_elses.id)],
        links={somebody_elses.id: [scheduling.id]},
    )

    assert use_case.search(scheduling.id).outcome is TopicNoteSearchOutcome.NO_LINKED_MATERIAL


# -- the three empty answers --------------------------------------------------


def test_no_linked_material_is_told_apart_from_no_notes(owner, scheduling):
    bare = a_resource(owner)
    use_case, _ = build(owner, scheduling, resources=[bare], links={bare.id: [scheduling.id]})

    assert use_case.search(scheduling.id).outcome is TopicNoteSearchOutcome.NO_ACTIVE_NOTES


def test_notes_that_mention_nothing_are_told_apart_from_having_no_notes(owner, scheduling):
    resource = a_resource(owner)
    unrelated = a_note(resource.id, title="Groceries", body="Milk and bread.")
    use_case, _ = build(
        owner,
        scheduling,
        resources=[resource],
        notes=[unrelated],
        links={resource.id: [scheduling.id]},
    )

    assert use_case.search(scheduling.id).outcome is TopicNoteSearchOutcome.NO_MATCHING_PASSAGE


def test_every_empty_answer_carries_no_passages(owner, scheduling):
    use_case, _ = build(owner, scheduling)

    result = use_case.search(scheduling.id)

    assert result.outcome is TopicNoteSearchOutcome.NO_LINKED_MATERIAL
    assert result.passages == ()


def test_a_search_is_not_run_when_there_is_nothing_to_search(owner, scheduling):
    """The cheap checks come first, so an empty catalogue costs no query."""
    use_case, search = build(owner, scheduling)

    use_case.search(scheduling.id)

    assert search.searches == []


# -- refusals -----------------------------------------------------------------


def test_an_unknown_topic_is_refused(owner, scheduling):
    use_case, _ = build(owner, scheduling)

    with pytest.raises(UnknownTopicError):
        use_case.search(uuid.uuid4())


def test_a_search_before_setup_is_refused(scheduling):
    use_case = RetrieveTopicNotes(
        learners=FakeLearnerRepository(()),
        resources=FakeResourceRepository(topics=[scheduling]),
        notes=FakeNoteSearchRepository(topics=[scheduling]),
    )

    with pytest.raises(LearnerNotSetUpError):
        use_case.search(scheduling.id)


def test_more_than_one_stored_learner_is_refused(owner, scheduling):
    use_case = RetrieveTopicNotes(
        learners=FakeLearnerRepository((owner, learner())),
        resources=FakeResourceRepository(topics=[scheduling]),
        notes=FakeNoteSearchRepository(topics=[scheduling]),
    )

    with pytest.raises(AmbiguousLocalLearnerError):
        use_case.search(scheduling.id)


# -- what the search does not do ----------------------------------------------


def test_the_use_case_binds_no_provider_a_note_could_leave_through(owner, scheduling):
    """NFR-001, asserted rather than promised.

    Adding an AI, embedding, or retrieval provider to this constructor is the
    visible decision that would begin sending a learner's text somewhere, and
    this test is what makes it visible.
    """
    use_case, _ = build(owner, scheduling)

    assert set(vars(use_case)) == {"_learners", "_resources", "_notes"}


def test_searching_writes_nothing(owner, scheduling):
    resource = a_resource(owner)
    note = a_note(resource.id)
    use_case, search = build(
        owner, scheduling, resources=[resource], notes=[note], links={resource.id: [scheduling.id]}
    )

    use_case.search(scheduling.id)
    use_case.search(scheduling.id)

    assert search.notes == [note]
    assert search.resources == [resource]
    assert not hasattr(search, "record_search")


def test_the_same_request_returns_the_same_answer(owner, scheduling):
    resource = a_resource(owner)
    use_case, _ = build(
        owner,
        scheduling,
        resources=[resource],
        notes=[a_note(resource.id), a_note(resource.id, title="Second")],
        links={resource.id: [scheduling.id]},
    )

    first = use_case.search(scheduling.id)
    second = use_case.search(scheduling.id)

    assert [p.note_id for p in first.passages] == [p.note_id for p in second.passages]


# -- the query the topic supplies ---------------------------------------------


def test_a_topic_name_becomes_its_words_joined_by_or():
    """`or` rather than an implicit `and`, so one word may match.

    `websearch_to_tsquery` reads adjacent words as *all must appear*, which would
    make a topic called CPU scheduling miss a note that only says "scheduler".
    """
    assert search_terms_for("CPU scheduling") == "cpu or scheduling"


def test_punctuation_in_a_topic_name_cannot_become_query_syntax():
    """A topic name is data. Quotation marks and dashes are operators to
    `websearch_to_tsquery`, so they are stripped rather than escaped."""
    assert search_terms_for('B-Trees and "Indexing"') == "b or trees or indexing"


def test_a_conjunction_in_a_topic_name_is_not_carried_into_the_query():
    assert search_terms_for("Search and Sorting") == "search or sorting"


def test_a_topic_name_with_no_words_yields_no_terms():
    assert search_terms_for("—") == ""


def test_digits_in_a_topic_name_are_kept():
    assert search_terms_for("IPv6 addressing") == "ipv6 or addressing"


# -- a passage is an exact substring ------------------------------------------


def test_a_passage_is_always_an_exact_substring_of_the_note(owner, scheduling):
    """The property the whole extractor exists for.

    Not "close to" the note and not "the note with markup stripped": the passage
    must appear in the body character for character.
    """
    resource = a_resource(owner)
    body = "Scheduling in C++: use std::vector<int> and a < b, then a>>b for the shift."
    use_case, _ = build(
        owner,
        scheduling,
        resources=[resource],
        notes=[a_note(resource.id, body=body)],
        links={resource.id: [scheduling.id]},
    )

    passage = use_case.search(scheduling.id).passages[0].passage

    assert passage in body
    assert "vector<int>" in passage
    assert "a < b" in passage
    assert "a>>b" in passage


@pytest.mark.parametrize(
    "body",
    [
        "Scheduling uses vector<int> for the ready queue.",
        "Scheduling: if (a < b) { swap(a, b); }",
        "Scheduling — see <https://example.test/notes> for more.",
        "Scheduling & dispatch <em>are</em> different things.",
        "Scheduling\n\n\tvector<pair<int, int>> ready;\n\ndone.",
        "Scheduling 100% of the time <>&\"'` survive.",
    ],
)
def test_code_like_and_literal_text_survives_unchanged(owner, scheduling, body):
    resource = a_resource(owner)
    use_case, _ = build(
        owner,
        scheduling,
        resources=[resource],
        notes=[a_note(resource.id, body=body)],
        links={resource.id: [scheduling.id]},
    )

    passage = use_case.search(scheduling.id).passages[0].passage

    # Short bodies come back whole, so nothing may be lost at all.
    assert passage == body.strip()


def test_nothing_is_inserted_between_parts_of_a_passage(owner, scheduling):
    """One contiguous window, so no separator is ever added.

    Joining fragments would put a character in the passage that the learner did
    not write, which is what stops it being their text.
    """
    resource = a_resource(owner)
    body = (
        "Scheduling appears here. "
        + ("filler word " * 200)
        + "and scheduling appears again far below."
    )
    use_case, _ = build(
        owner,
        scheduling,
        resources=[resource],
        notes=[a_note(resource.id, body=body)],
        links={resource.id: [scheduling.id]},
    )

    passage = use_case.search(scheduling.id).passages[0].passage

    assert passage in body
    assert "…" not in passage
    assert "..." not in passage


def test_searching_never_changes_the_stored_note(owner, scheduling):
    resource = a_resource(owner)
    body = "Scheduling with vector<int> and <b>bold</b> markup."
    note = a_note(resource.id, body=body)
    use_case, search = build(
        owner, scheduling, resources=[resource], notes=[note], links={resource.id: [scheduling.id]}
    )

    use_case.search(scheduling.id)
    use_case.search(scheduling.id)

    assert search.notes[0].body == body
    assert search.notes[0] is note


# -- how the window is chosen -------------------------------------------------


def test_a_short_note_comes_back_whole():
    assert extract_passage("Scheduling is fair.", "scheduling") == "Scheduling is fair."


def test_a_long_note_is_cut_to_a_window_around_the_match():
    body = ("alpha " * 300) + "scheduling matters " + ("omega " * 300)

    passage = extract_passage(body, "scheduling")

    assert passage in body
    assert "scheduling matters" in passage
    assert len(passage.split()) <= MAX_PASSAGE_WORDS


def test_the_window_keeps_some_run_up_before_the_match():
    """A passage that began exactly at the match would read as mid-thought."""
    body = ("alpha " * 50) + "scheduling matters " + ("omega " * 50)

    passage = extract_passage(body, "scheduling")

    assert passage.startswith("alpha")
    assert passage in body


def test_stemmed_words_are_located_so_the_window_lands_on_them():
    """PostgreSQL matched "schedulers" for "scheduling"; the cut follows it."""
    body = ("alpha " * 100) + "schedulers pick a process " + ("omega " * 100)

    passage = extract_passage(body, "cpu or scheduling")

    assert "schedulers pick a process" in passage
    assert passage in body


def test_an_unlocatable_match_falls_back_to_the_start_of_the_note():
    """Honest, and still exact.

    PostgreSQL's stemmer may match something this approximation cannot see. The
    passage is then the note's opening rather than a guess.
    """
    body = "Alpha beta gamma delta. " + ("filler " * 100)

    passage = extract_passage(body, "scheduling")

    assert body.startswith(passage)
    assert passage in body


def test_a_note_with_no_words_comes_back_as_it_is():
    assert extract_passage("—— ——", "scheduling") == "—— ——"


def test_the_query_operator_word_never_becomes_a_match_target():
    """`or` joins the terms; it must not be what a window is centred on."""
    body = ("alpha or beta " * 40) + "scheduling here"

    passage = extract_passage(body, "cpu or scheduling")

    assert "scheduling here" in passage
