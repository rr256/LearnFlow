"""Answering a learner's question from their own notes (MNT-001).

The first **mentor** capability in LearnFlow, and the first code anywhere in it
that asks a model anything. It completes what
[ADR-037](../../../../docs/adr/ADR-037-learner-written-resource-notes.md) and
[ADR-038](../../../../docs/adr/ADR-038-local-topic-note-retrieval.md) built
towards, and is contracted by
[ADR-039](../../../../docs/adr/ADR-039-source-grounded-study-answers.md).

**Retrieval decides whether a model is asked at all.** The order here is not an
implementation detail: passages are retrieved first, and the provider is reached
**only** on the branch where retrieval found some. With nothing found there is no
prompt, no request, and no outbound call — LearnFlow says it has nothing of the
learner's to answer from. That is the difference between a grounded mentor and a
chatbot with a citation section, and it is asserted directly by tests that fail
if the provider records a single call.

**It answers from the learner's notes, not from the model's memory.** The
instruction sent with a prompt says so, but the guarantee that matters is
structural: the provider is handed a `GroundedAnswerRequest` and nothing else, so
the learner's stored material reaches it only as the passages retrieval chose.

**The citations are recorded from what was sent.** They are captured before the
provider is asked and returned unchanged, so an answer cannot cite a note that
was not consulted. The model is never invited to name a source and is given no
identifier with which to name one.

**It reuses retrieval rather than repeating it.** `RetrieveTopicNotes` already
resolves the learner, checks the topic, enforces ownership, and cuts exact
substrings; a second implementation of any of that would be a second place for
the ownership rule to drift.

**It writes nothing at all.** No question, no answer, no history, no learning
stage, no plan, no plan item, no revision, and no quiz. Asking twice leaves no
trace that either happened, and there is nothing to delete afterwards.

**A provider failure never costs the learner their own notes.** Every failure
branch returns the passages that were found, with an outcome naming what went
wrong, because the retrieval half succeeded and is worth reading on its own.
"""

import uuid

from app.application.dto.note_retrieval import (
    TopicNotePassage,
    TopicNoteSearchOutcome,
    TopicNoteSearchResult,
)
from app.application.dto.study_answer import (
    MAX_GROUNDING_PASSAGES,
    MAX_QUESTION_LENGTH,
    StudyAnswer,
    StudyAnswerOutcome,
)
from app.application.ports.ai_provider import (
    AIProvider,
    AIProviderModelMissingError,
    AIProviderTimedOutError,
    AIProviderUnavailableError,
    AIProviderUnusableReplyError,
    GroundedAnswerRequest,
)
from app.application.use_cases.retrieve_topic_notes import (
    RetrieveTopicNotes,
    TopicNoteRetrievalError,
)


class StudyAnswerError(Exception):
    """Base class for the refusals this use case makes before retrieval runs."""


class EmptyQuestionError(StudyAnswerError):
    """A question that is blank, or is only whitespace.

    Refused rather than sent. A provider asked an empty question answers from
    nothing, which is precisely what this endpoint exists to prevent.
    """


class QuestionTooLongError(StudyAnswerError):
    """A question longer than `MAX_QUESTION_LENGTH`."""


_RETRIEVAL_OUTCOMES: dict[TopicNoteSearchOutcome, StudyAnswerOutcome] = {
    TopicNoteSearchOutcome.NO_LINKED_MATERIAL: StudyAnswerOutcome.NO_LINKED_MATERIAL,
    TopicNoteSearchOutcome.NO_ACTIVE_NOTES: StudyAnswerOutcome.NO_ACTIVE_NOTES,
    TopicNoteSearchOutcome.NO_MATCHING_PASSAGE: StudyAnswerOutcome.NO_MATCHING_PASSAGE,
}
"""Retrieval's empty answers, carried through unchanged.

Mapped rather than reused directly so the two contracts can diverge later without
one silently redefining the other, and stated as data so a retrieval outcome
added later fails loudly here rather than being read as grounds to answer.
"""

_PROVIDER_FAILURES: dict[type[Exception], StudyAnswerOutcome] = {
    AIProviderUnavailableError: StudyAnswerOutcome.PROVIDER_UNAVAILABLE,
    AIProviderModelMissingError: StudyAnswerOutcome.PROVIDER_UNAVAILABLE,
    AIProviderTimedOutError: StudyAnswerOutcome.PROVIDER_TIMED_OUT,
    AIProviderUnusableReplyError: StudyAnswerOutcome.PROVIDER_UNUSABLE_REPLY,
}
"""How each provider failure is reported.

A missing model and an unreachable provider share an outcome because both mean
"the provider cannot answer right now" to a learner reading the screen; the
adapter's message says which, and neither is an error the request caused.
"""


class AnswerTopicQuestion:
    """Answers one question about one topic from the learner's own notes.

    It binds exactly two collaborators: retrieval, which decides whether there is
    anything to answer from, and one AI provider. Nothing else — no clock, no
    configuration, no writer of any kind — because this use case stores nothing
    and its answer does not depend on the date.
    """

    def __init__(self, *, retrieval: RetrieveTopicNotes, provider: AIProvider) -> None:
        """Bind the use case to retrieval and to the provider behind the port."""
        self._retrieval = retrieval
        self._provider = provider

    def answer(self, *, topic_id: uuid.UUID, question: str) -> StudyAnswer:
        """Answer a question about one topic, grounded in the learner's notes.

        **The provider is asked only when passages were found.** With none, this
        returns before any request is built: no prompt is composed and nothing
        leaves the process. A learner is told which of the three empty cases
        applies, because linking material, writing a note, and trying another
        topic are different next steps.

        The passages returned are the ones the answer was grounded in — the same
        exact substrings retrieval produced, unmodified. They come back on the
        failure branches too, so a provider that is switched off costs the learner
        an answer and not the reading of their own notes.

        Nothing is written, and nothing else moves.

        Args:
            topic_id: The curriculum topic the question is about.
            question: What the learner typed. Sent verbatim; never stored.

        Raises:
            EmptyQuestionError: The question is blank or only whitespace.
            QuestionTooLongError: The question exceeds `MAX_QUESTION_LENGTH`.
            LearnerNotSetUpError: No learner is stored yet.
            UnknownTopicError: The topic identifier names nothing stored.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        asked = _require_question(question)
        found = self._retrieval.search(topic_id)

        if found.outcome is not TopicNoteSearchOutcome.FOUND:
            # The whole point of the feature: no evidence, no model call. The
            # provider is not touched on this path, and a test asserts it.
            return _without_answer(found, asked, _RETRIEVAL_OUTCOMES[found.outcome])

        # Captured before the provider is asked, so the citations describe what
        # was consulted rather than what the model afterwards claimed.
        grounds = found.passages[:MAX_GROUNDING_PASSAGES]
        request = GroundedAnswerRequest(
            question=asked,
            topic_name=found.topic_name,
            subject_name=found.subject_name,
            passages=tuple(passage.passage for passage in grounds),
        )

        try:
            prose = self._provider.generate_answer(request)
        except tuple(_PROVIDER_FAILURES) as failure:
            return _without_answer(found, asked, _PROVIDER_FAILURES[type(failure)], grounds)

        return StudyAnswer(
            topic_id=found.topic_id,
            topic_name=found.topic_name,
            subject_name=found.subject_name,
            question=asked,
            outcome=StudyAnswerOutcome.ANSWERED,
            answer=prose,
            passages=grounds,
        )


def _require_question(question: str) -> str:
    """The question as it will be sent, or a refusal.

    Trimmed of surrounding whitespace only. What the learner wrote inside their
    question is theirs and is sent character for character — the same respect for
    stored text that keeps a passage an exact substring.
    """
    asked = question.strip()
    if not asked:
        raise EmptyQuestionError("A question is required.")
    if len(asked) > MAX_QUESTION_LENGTH:
        raise QuestionTooLongError(f"A question may be at most {MAX_QUESTION_LENGTH} characters.")
    return asked


def _without_answer(
    found: TopicNoteSearchResult,
    question: str,
    outcome: StudyAnswerOutcome,
    passages: tuple[TopicNotePassage, ...] = (),
) -> StudyAnswer:
    """A result carrying no answer, with the topic context retrieval established."""
    return StudyAnswer(
        topic_id=found.topic_id,
        topic_name=found.topic_name,
        subject_name=found.subject_name,
        question=question,
        outcome=outcome,
        answer=None,
        passages=passages,
    )


__all__ = [
    "AnswerTopicQuestion",
    "EmptyQuestionError",
    "QuestionTooLongError",
    "StudyAnswerError",
    "TopicNoteRetrievalError",
]
