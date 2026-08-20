"""The rules a source-grounded study answer follows (MNT-001).

The first group is the feature's central promise and the reason it exists:
**with nothing retrieved, the provider is never asked.** Those tests fail if a
single request reaches the port, so a future change that answers from a model's
own training cannot pass quietly.

The second group is the privacy boundary: exactly what may be sent, asserted
against the payload itself rather than against a docstring.

Nothing here reaches a network. The provider is always `FakeAIProvider`.
"""

import uuid

import pytest

from app.application.dto.note_retrieval import TopicNoteSearchOutcome
from app.application.dto.resource import ResourceRecord
from app.application.dto.resource_note import ResourceNoteRecord
from app.application.dto.study_answer import (
    ANSWERLESS_OUTCOMES,
    MAX_GROUNDING_PASSAGES,
    MAX_QUESTION_LENGTH,
    UNGROUNDED_OUTCOMES,
    StudyAnswerOutcome,
)
from app.application.ports.ai_provider import (
    AIProviderModelMissingError,
    AIProviderTimedOutError,
    AIProviderUnavailableError,
    AIProviderUnusableReplyError,
)
from app.application.use_cases.answer_topic_question import (
    AnswerTopicQuestion,
    EmptyQuestionError,
    QuestionTooLongError,
)
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.retrieve_topic_notes import (
    LearnerNotSetUpError,
    RetrieveTopicNotes,
    UnknownTopicError,
)
from tests.unit.fake_ai_provider import FakeAIProvider
from tests.unit.fake_learner_repository import FakeLearnerRepository, learner
from tests.unit.fake_note_search_repository import FakeNoteSearchRepository
from tests.unit.fake_resource_repository import FakeResourceRepository, resource_topic

QUESTION = "How does round robin decide which process runs next?"


@pytest.fixture
def owner():
    """The local learner whose notes are consulted."""
    return learner()


@pytest.fixture
def scheduling():
    """The topic every question in these tests is asked about."""
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
    body: str = "Round robin scheduling gives each process a fixed quantum.",
    status: str = "active",
) -> ResourceNoteRecord:
    """One note on that material."""
    return ResourceNoteRecord(
        id=uuid.uuid4(), resource_id=resource_id, title=title, body=body, status=status
    )


def build(
    owner_record,
    topic,
    *,
    resources=(),
    notes=(),
    links=None,
    provider: FakeAIProvider | None = None,
    learners=None,
):
    """A use case over one learner's material, with a fake provider behind it."""
    ai = provider or FakeAIProvider()
    retrieval = RetrieveTopicNotes(
        learners=learners or FakeLearnerRepository((owner_record,)),
        resources=FakeResourceRepository(topics=[topic]),
        notes=FakeNoteSearchRepository(
            resources=resources, notes=notes, topics=[topic], links=links or {}
        ),
    )
    return AnswerTopicQuestion(retrieval=retrieval, provider=ai), ai


def grounded(owner_record, topic, *, body: str | None = None, provider=None):
    """A use case whose learner has one note that does mention the topic."""
    resource = a_resource(owner_record)
    note = a_note(resource.id) if body is None else a_note(resource.id, body=body)
    use_case, ai = build(
        owner_record,
        topic,
        resources=[resource],
        notes=[note],
        links={resource.id: [topic.id]},
        provider=provider,
    )
    return use_case, ai, note, resource


# -- no evidence, no model call ----------------------------------------------
#
# The feature's central promise. Each of these asserts the negative directly:
# the provider recorded nothing.


def test_no_linked_material_never_reaches_the_provider(owner, scheduling):
    use_case, ai = build(owner, scheduling)

    result = use_case.answer(topic_id=scheduling.id, question=QUESTION)

    assert result.outcome is StudyAnswerOutcome.NO_LINKED_MATERIAL
    assert ai.was_asked is False
    assert ai.requests == []


def test_no_active_note_never_reaches_the_provider(owner, scheduling):
    resource = a_resource(owner)
    archived = a_note(resource.id, status="archived")
    use_case, ai = build(
        owner,
        scheduling,
        resources=[resource],
        notes=[archived],
        links={resource.id: [scheduling.id]},
    )

    result = use_case.answer(topic_id=scheduling.id, question=QUESTION)

    assert result.outcome is StudyAnswerOutcome.NO_ACTIVE_NOTES
    assert ai.was_asked is False


def test_no_matching_passage_never_reaches_the_provider(owner, scheduling):
    # The case the whole feature turns on: the learner has notes, and none of
    # them is about this. Answering here would be answering from the model.
    resource = a_resource(owner)
    unrelated = a_note(resource.id, title="Networks", body="TCP retransmits lost segments.")
    use_case, ai = build(
        owner,
        scheduling,
        resources=[resource],
        notes=[unrelated],
        links={resource.id: [scheduling.id]},
    )

    result = use_case.answer(topic_id=scheduling.id, question=QUESTION)

    assert result.outcome is StudyAnswerOutcome.NO_MATCHING_PASSAGE
    assert ai.was_asked is False
    assert result.answer is None
    assert result.passages == ()


def test_every_ungrounded_outcome_is_reachable_without_a_provider_call(owner, scheduling):
    """The three ungrounded outcomes are exactly the ones reached with no call.

    Asserted as a set so an outcome added later is not quietly left out of the
    promise: if a fourth ungrounded case appears, this fails until it is covered.
    """
    reached = set()

    empty, ai_empty = build(owner, scheduling)
    reached.add(empty.answer(topic_id=scheduling.id, question=QUESTION).outcome)

    resource = a_resource(owner)
    archived, ai_archived = build(
        owner,
        scheduling,
        resources=[resource],
        notes=[a_note(resource.id, status="archived")],
        links={resource.id: [scheduling.id]},
    )
    reached.add(archived.answer(topic_id=scheduling.id, question=QUESTION).outcome)

    other = a_resource(owner)
    unrelated, ai_unrelated = build(
        owner,
        scheduling,
        resources=[other],
        notes=[a_note(other.id, title="Networks", body="TCP retransmits segments.")],
        links={other.id: [scheduling.id]},
    )
    reached.add(unrelated.answer(topic_id=scheduling.id, question=QUESTION).outcome)

    assert reached == UNGROUNDED_OUTCOMES
    assert not any(ai.was_asked for ai in (ai_empty, ai_archived, ai_unrelated))


# -- what is sent -------------------------------------------------------------


def test_only_the_question_topic_and_passages_are_sent(owner, scheduling):
    use_case, ai, note, resource = grounded(owner, scheduling)

    use_case.answer(topic_id=scheduling.id, question=QUESTION)

    sent = ai.requests[0]
    assert sent.question == QUESTION
    assert sent.topic_name == "CPU scheduling"
    assert sent.subject_name == "Operating Systems"
    assert sent.passages == ("Round robin scheduling gives each process a fixed quantum.",)


def test_no_identifier_of_any_kind_leaves_the_process(owner, scheduling):
    """The privacy boundary, asserted against the payload rather than the docs.

    Every identifier the result carries is checked against everything the request
    holds, so adding a field to `GroundedAnswerRequest` that carries one fails
    here rather than being noticed in review.
    """
    use_case, ai, note, resource = grounded(owner, scheduling)

    result = use_case.answer(topic_id=scheduling.id, question=QUESTION)

    sent = ai.requests[0]
    everything = " ".join((sent.question, sent.topic_name, sent.subject_name, *sent.passages))
    for identifier in (owner.id, note.id, resource.id, scheduling.id, result.topic_id):
        assert str(identifier) not in everything


def test_no_note_or_resource_title_is_sent(owner, scheduling):
    # A title is the learner's own words about how they organise their study,
    # and the model needs none of it to answer from a passage.
    use_case, ai, note, resource = grounded(owner, scheduling)

    use_case.answer(topic_id=scheduling.id, question=QUESTION)

    everything = " ".join((*ai.requests[0].passages, ai.requests[0].question))
    assert note.title not in everything
    assert resource.title not in everything


def test_the_request_carries_no_field_beyond_the_four(owner, scheduling):
    """The structure itself is the boundary, so its shape is pinned.

    A field added to `GroundedAnswerRequest` is a decision about what may leave
    the machine, and this fails until someone changes this test deliberately.
    """
    use_case, ai, _, _ = grounded(owner, scheduling)

    use_case.answer(topic_id=scheduling.id, question=QUESTION)

    assert set(type(ai.requests[0]).__slots__) == {
        "question",
        "topic_name",
        "subject_name",
        "passages",
    }


def test_a_passage_is_sent_exactly_as_it_was_retrieved(owner, scheduling):
    # Code-like text survives into the prompt for the same reason it survives
    # onto the screen: nothing between the note and the model rewrites it.
    body = "Scheduling queues use vector<int> and a < b comparisons."
    use_case, ai, _, _ = grounded(owner, scheduling, body=body)

    result = use_case.answer(topic_id=scheduling.id, question=QUESTION)

    assert "vector<int>" in ai.requests[0].passages[0]
    assert ai.requests[0].passages[0] == result.passages[0].passage


def test_no_more_than_the_grounding_limit_of_passages_is_sent(owner, scheduling):
    resource = a_resource(owner)
    notes = [
        a_note(resource.id, title=f"Note {index}", body=f"Scheduling note number {index}.")
        for index in range(MAX_GROUNDING_PASSAGES + 4)
    ]
    use_case, ai = build(
        owner,
        scheduling,
        resources=[resource],
        notes=notes,
        links={resource.id: [scheduling.id]},
    )

    result = use_case.answer(topic_id=scheduling.id, question=QUESTION)

    assert len(ai.requests[0].passages) == MAX_GROUNDING_PASSAGES
    # The citations describe what was sent, so they are bounded the same way.
    assert len(result.passages) == MAX_GROUNDING_PASSAGES


# -- the answer and its citations --------------------------------------------


def test_an_answer_comes_back_with_the_passages_it_was_grounded_in(owner, scheduling):
    use_case, _, note, resource = grounded(owner, scheduling)

    result = use_case.answer(topic_id=scheduling.id, question=QUESTION)

    assert result.outcome is StudyAnswerOutcome.ANSWERED
    assert result.answer == "Round robin gives each process a fixed quantum."
    assert len(result.passages) == 1
    assert result.passages[0].note_id == note.id
    assert result.passages[0].resource_title == resource.title


def test_the_citations_are_what_was_sent_not_what_the_model_said(owner, scheduling):
    # The model names a note that was never consulted. Nothing reads a source out
    # of the prose, so the citation list is unaffected.
    invents = FakeAIProvider(answer="According to your note 'Deadlocks', quanta are fixed.")
    use_case, _, note, _ = grounded(owner, scheduling, provider=invents)

    result = use_case.answer(topic_id=scheduling.id, question=QUESTION)

    assert [passage.note_id for passage in result.passages] == [note.id]
    assert result.passages[0].note_title == "Scheduling"


def test_the_question_is_echoed_back_as_it_was_asked(owner, scheduling):
    use_case, _, _, _ = grounded(owner, scheduling)

    result = use_case.answer(topic_id=scheduling.id, question=f"  {QUESTION}  ")

    assert result.question == QUESTION


def test_the_topic_is_named_on_the_result(owner, scheduling):
    use_case, _, _, _ = grounded(owner, scheduling)

    result = use_case.answer(topic_id=scheduling.id, question=QUESTION)

    assert result.topic_id == scheduling.id
    assert result.topic_name == "CPU scheduling"
    assert result.subject_name == "Operating Systems"


# -- provider failures --------------------------------------------------------


@pytest.mark.parametrize(
    ("failure", "outcome"),
    [
        (AIProviderUnavailableError("unreachable"), StudyAnswerOutcome.PROVIDER_UNAVAILABLE),
        (AIProviderModelMissingError("no model"), StudyAnswerOutcome.PROVIDER_UNAVAILABLE),
        (AIProviderTimedOutError("too slow"), StudyAnswerOutcome.PROVIDER_TIMED_OUT),
        (AIProviderUnusableReplyError("empty"), StudyAnswerOutcome.PROVIDER_UNUSABLE_REPLY),
    ],
)
def test_a_provider_failure_is_reported_and_keeps_the_passages(owner, scheduling, failure, outcome):
    use_case, _, note, _ = grounded(owner, scheduling, provider=FakeAIProvider(fails_with=failure))

    result = use_case.answer(topic_id=scheduling.id, question=QUESTION)

    assert result.outcome is outcome
    assert result.answer is None
    # The retrieval half succeeded, so the learner still gets their own notes.
    assert [passage.note_id for passage in result.passages] == [note.id]


def test_a_provider_failure_is_not_raised_out_of_the_use_case(owner, scheduling):
    # A learner asking a question when Ollama is switched off gets an answer
    # about the provider, not a stack trace.
    use_case, _, _, _ = grounded(
        owner, scheduling, provider=FakeAIProvider(fails_with=AIProviderUnavailableError("off"))
    )

    result = use_case.answer(topic_id=scheduling.id, question=QUESTION)

    assert result.outcome in ANSWERLESS_OUTCOMES


def test_the_provider_is_asked_once_and_not_retried(owner, scheduling):
    slow = FakeAIProvider(fails_with=AIProviderTimedOutError("too slow"))
    use_case, ai, _, _ = grounded(owner, scheduling, provider=slow)

    use_case.answer(topic_id=scheduling.id, question=QUESTION)

    assert len(ai.requests) == 1


# -- refusals -----------------------------------------------------------------


@pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
def test_a_blank_question_is_refused_before_anything_is_read(owner, scheduling, blank):
    use_case, ai, _, _ = grounded(owner, scheduling)

    with pytest.raises(EmptyQuestionError):
        use_case.answer(topic_id=scheduling.id, question=blank)

    assert ai.was_asked is False


def test_a_question_longer_than_the_limit_is_refused(owner, scheduling):
    use_case, ai, _, _ = grounded(owner, scheduling)

    with pytest.raises(QuestionTooLongError):
        use_case.answer(topic_id=scheduling.id, question="x" * (MAX_QUESTION_LENGTH + 1))

    assert ai.was_asked is False


def test_a_question_at_the_limit_is_accepted(owner, scheduling):
    use_case, _, _, _ = grounded(owner, scheduling)

    result = use_case.answer(topic_id=scheduling.id, question="scheduling " * 90)

    assert result.outcome is StudyAnswerOutcome.ANSWERED


def test_an_unknown_topic_is_refused_without_asking_the_provider(owner, scheduling):
    use_case, ai, _, _ = grounded(owner, scheduling)

    with pytest.raises(UnknownTopicError):
        use_case.answer(topic_id=uuid.uuid4(), question=QUESTION)

    assert ai.was_asked is False


def test_no_learner_is_refused_without_asking_the_provider(scheduling):
    use_case, ai = build(learner(), scheduling, learners=FakeLearnerRepository(()))

    with pytest.raises(LearnerNotSetUpError):
        use_case.answer(topic_id=scheduling.id, question=QUESTION)

    assert ai.was_asked is False


def test_more_than_one_learner_is_refused_without_asking_the_provider(scheduling):
    use_case, ai = build(
        learner(), scheduling, learners=FakeLearnerRepository((learner(), learner()))
    )

    with pytest.raises(AmbiguousLocalLearnerError):
        use_case.answer(topic_id=scheduling.id, question=QUESTION)

    assert ai.was_asked is False


# -- what does not happen -----------------------------------------------------


def test_asking_twice_stores_nothing_and_changes_nothing(owner, scheduling):
    use_case, ai, _, _ = grounded(owner, scheduling)

    first = use_case.answer(topic_id=scheduling.id, question=QUESTION)
    second = use_case.answer(topic_id=scheduling.id, question=QUESTION)

    assert first == second
    assert len(ai.requests) == 2


def test_the_use_case_binds_no_writer_of_any_kind(owner, scheduling):
    """Nothing on this use case can write, so nothing can be stored by accident.

    The two collaborators are retrieval, which never commits, and the provider.
    A repository added here would be the visible decision that changed it.
    """
    use_case, _, _, _ = grounded(owner, scheduling)

    bound = {name for name in vars(use_case)}

    assert bound == {"_retrieval", "_provider"}


def test_every_answerless_outcome_carries_no_answer(owner, scheduling):
    """Derived from the enum, so a new outcome is covered without being listed."""
    assert StudyAnswerOutcome.ANSWERED not in ANSWERLESS_OUTCOMES
    assert UNGROUNDED_OUTCOMES <= ANSWERLESS_OUTCOMES


def test_retrieval_outcomes_map_one_to_one_onto_answer_outcomes():
    """Every empty retrieval outcome has somewhere to go.

    A retrieval outcome added later without a mapping would otherwise raise a
    `KeyError` at the first question a learner asked.
    """
    from app.application.use_cases.answer_topic_question import _RETRIEVAL_OUTCOMES

    empty = {
        outcome for outcome in TopicNoteSearchOutcome if outcome is not TopicNoteSearchOutcome.FOUND
    }

    assert set(_RETRIEVAL_OUTCOMES) == empty
