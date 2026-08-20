"""Input and output structures for a source-grounded study answer (MNT-001).

These carry what the first **mentor** endpoint returns. They are
framework-independent by design, as the other DTOs in this package are.

**An answer never travels without its grounds.** `StudyAnswer` carries the
passages the answer was built from in the same structure as the answer itself,
so there is no code path that returns prose alone. That is what makes a citation
a property of the result rather than something a screen has to remember to
render.

**The citations are LearnFlow's, not the model's.** They are the passages that
were retrieved and sent, recorded before the provider was asked; the model is
never invited to name a source and could not, since it is given no identifier.
An answer therefore cannot cite a note that was not consulted, which is the
failure mode `docs/rag/retrieval.md` warns about when it forbids claiming an
answer is grounded when retrieval did not succeed.

**Nothing here is stored.** No question, no answer, and no record that either
happened. These structures exist for the length of one request
([ADR-039](../../../../docs/adr/ADR-039-source-grounded-study-answers.md)).

**Nothing here measures the learner.** No score, no confidence figure, no
relevance number, and no count of passages — a figure beside a learner's own
writing reads as a mark on it, which is the line
`docs/domain/terminology.md` draws.
"""

import uuid
from dataclasses import dataclass
from enum import Enum

from app.application.dto.note_retrieval import TopicNotePassage


class StudyAnswerOutcome(Enum):
    """What became of one question, and why.

    Every empty answer is told apart rather than collapsed, for the reason
    `TopicNoteSearchOutcome` gives: they ask the learner to do different things.
    Here that matters more, because three of them mean **the model was never
    asked** and two mean it was asked and could not reply — and a learner who
    cannot tell those apart does not know whether their notes or their setup is
    the problem.
    """

    ANSWERED = "answered"
    """Passages were found, the provider was asked, and it replied."""

    NO_LINKED_MATERIAL = "no_linked_material"
    """The learner has linked no material to this topic. **No model call.**"""

    NO_ACTIVE_NOTES = "no_active_notes"
    """Material is linked and carries no active note. **No model call.**"""

    NO_MATCHING_PASSAGE = "no_matching_passage"
    """Active notes exist and none mentions the topic. **No model call.**

    This is the case the whole feature turns on: LearnFlow has nothing of the
    learner's to ground an answer in, so it says so rather than answering from
    the model's own training. Answering here would produce exactly the confident,
    unsourced text a grounded mentor exists to avoid.
    """

    PROVIDER_UNAVAILABLE = "provider_unavailable"
    """The AI provider could not be reached, or lacks the configured model.

    The retrieved passages are still returned: a provider that is switched off
    must not cost the learner the reading of their own notes.
    """

    PROVIDER_TIMED_OUT = "provider_timed_out"
    """The provider was reached and did not answer in time. Passages still returned."""

    PROVIDER_UNUSABLE_REPLY = "provider_unusable_reply"
    """The provider replied with nothing usable. Passages still returned."""


ANSWERLESS_OUTCOMES: frozenset[StudyAnswerOutcome] = frozenset(
    outcome for outcome in StudyAnswerOutcome if outcome is not StudyAnswerOutcome.ANSWERED
)
"""Every outcome that carries no answer.

Derived from the enum rather than listed, so an outcome added later is covered
without anyone remembering to add it here.
"""

UNGROUNDED_OUTCOMES: frozenset[StudyAnswerOutcome] = frozenset(
    {
        StudyAnswerOutcome.NO_LINKED_MATERIAL,
        StudyAnswerOutcome.NO_ACTIVE_NOTES,
        StudyAnswerOutcome.NO_MATCHING_PASSAGE,
    }
)
"""The outcomes reached **without asking the provider anything**.

Named as a set because it is the feature's central promise and is asserted
directly by tests: reaching one of these means no request left the process.
"""


@dataclass(frozen=True, slots=True)
class StudyAnswer:
    """What MNT-001 answers with.

    `answer` is set for exactly one outcome, `ANSWERED`, and `passages` is empty
    for exactly the three ungrounded ones. A provider failure keeps its passages,
    because the learner's own notes were found and are worth reading whether or
    not a model was able to comment on them.

    There is **no score, no confidence, no relevance figure, and no count**. The
    passages are the evidence; how many there are is not a fact about the learner
    worth reporting.

    Attributes:
        topic_id: The topic asked about, echoed so a caller can join without
            holding the request.
        topic_name: That topic's name.
        subject_name: The subject it belongs to.
        question: What the learner asked, echoed back verbatim so a result reads
            as an answer to something rather than as free-floating prose.
        outcome: Why this is the answer. See `StudyAnswerOutcome`.
        answer: The provider's prose, as plain text, or `None` when there is
            none. Never markup.
        passages: The learner's own words the answer was grounded in — the same
            exact substrings retrieval returned, with the note and resource they
            came from named. These are the citations, and they are recorded from
            what was **sent**, never from what the model claimed.
    """

    topic_id: uuid.UUID
    topic_name: str
    subject_name: str
    question: str
    outcome: StudyAnswerOutcome
    answer: str | None = None
    passages: tuple[TopicNotePassage, ...] = ()


MAX_QUESTION_LENGTH = 1_000
"""How long a question may be.

A bound on one request, not a judgement about what is worth asking. It exists
because the question is sent verbatim to a provider, and an unbounded field on an
endpoint that makes an outbound call is how a request body becomes a way to send
arbitrary text somewhere.

Generous enough for any real question about one topic, and far below
`MAX_NOTE_BODY_LENGTH`: a question is a question, and a learner with a page of
text to store has notes for that.
"""

MAX_GROUNDING_PASSAGES = 8
"""How many passages one answer is grounded in.

Fewer than `MAX_PASSAGES`, which bounds what a learner may *read*. This bounds
what is **sent**, and the two are different questions: a learner scrolling twenty
passages costs nothing, while twenty passages in a prompt crowd out the question
on a local model's context window and slow every answer.

The passages taken are the **first** ones, which are the most relevant — the only
thing relevance decides. Nothing is reordered, weighted, or dropped on any other
basis, and the figure is never reported to the learner.
"""
