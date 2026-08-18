"""Input and output structures for checkpoint practice: questions, quizzes, and attempts.

These carry what QZ-001 to QZ-010 write, assemble, and read back. They are
framework-independent by design, as the other DTOs in this package are: the API
schemas that serialise them are a separate representation, so a change to the
HTTP contract does not reach back into the use case.

`AnswerOption` and the marking outcomes are **imported from
`app.domain.checkpoint_marking`** rather than restated here. They are the shape
the marking rule works in, and copying them would create a second definition of
the same idea that could drift from the rule that decides it.

Nothing inbound carries a `learner_id`: the effective learner is resolved
server-side (docs/api/conventions.md).

The controlled values below mirror the `CHECK` constraints on the assessment
tables, the way the resource, plan, and revision vocabularies mirror theirs. A
value the application forgot to check is refused by the database rather than
stored and trusted later.

**No structure here carries a score, a mark, a total, or a count of correct
answers.** A result is a sequence of per-question outcomes, which is the shape
docs/domain/terminology.md requires and ADR-033 records.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain.checkpoint_marking import AnswerOption

MARKABLE_QUESTION_TYPES: tuple[str, ...] = ("multiple_choice",)
"""The question forms a learner may write, and this build can mark.

One of the four docs/database/schema.md documents. `multiple_select`, `numeric`,
and `short_answer` each need a marking rule that
`app.domain.checkpoint_marking` deliberately does not have — and `short_answer`
cannot have one at all without judging free text, which nothing here may do. The
`CHECK` on `questions.question_type` still carries all four, so offering one
later is a use-case change rather than a migration.
"""

QUESTION_STATUSES: tuple[str, ...] = ("ready", "retired")
"""The statuses a learner may set on a question, or filter by.

Two of the three docs/database/schema.md documents. `draft` is unreachable
because a question is written whole in one request; nothing composes one over
several, so a draft would be a state nothing could create or leave.

`ready` is a question a quiz may ask. `retired` is one the learner has set aside,
and it is **reversible** — nothing deletes a question, because every attempt
already marked against it references it.
"""

CURATED = "curated"
"""The `source_type` every question and quiz here is written with.

One of the three docs/database/schema.md documents. `generated` waits on an AI
provider, which does not exist and which nothing in this feature uses;
`verified_pyq` waits on verified previous-year content, which this repository
deliberately does not ship. The learner writes their own questions, so what is
stored is curated material.
"""

READY = "ready"
RETIRED = "retired"
IN_PROGRESS = "in_progress"
EVALUATED = "evaluated"

MAX_TOPIC_LINKS = 100
"""How many topics one question may name in a single request.

A bound rather than a rule about study: it stops one request writing an unbounded
number of rows. It sits above the 65 topics and subtopics of the whole curated
GATE CSE curriculum, so no honest link set is refused by it — the bound
`ResourceRecord` uses, for the same reason.
"""

MAX_QUIZ_TOPICS = 100
"""How many topics one quiz-assembly request may name.

The same kind of bound, applied to the request that assembles a quiz.
"""


@dataclass(frozen=True, slots=True)
class PracticeTopic:
    """A curriculum topic a question or a quiz covers, named well enough to display."""

    id: uuid.UUID
    code: str | None
    name: str
    subject_id: uuid.UUID
    subject_name: str


@dataclass(frozen=True, slots=True)
class QuestionRecord:
    """One practice question, as stored.

    The persistence shape, used by the port. `QuestionDetail` below is what a
    caller reads.

    `expected_option_key` is flattened out of the stored `expected_answer`
    payload here so that no layer above persistence has to know the `jsonb`
    shape. `written_at` is the question's `created_at`; it is carried because
    `arrange_questions` orders a quiz by it.

    There is no `difficulty`: nothing decides one, and a difficulty would rank
    one question above another.
    """

    id: uuid.UUID
    author_learner_id: uuid.UUID | None
    question_type: str
    source_type: str
    prompt: str
    options: tuple[AnswerOption, ...]
    expected_option_key: str
    explanation: str | None
    status: str
    written_at: datetime


@dataclass(frozen=True, slots=True)
class QuestionDetail:
    """One practice question as a learner reads it, with the topics it covers.

    `topics` is carried on a listed question as well as on a read one, for the
    reason `ResourceDetail` carries its own: a link set is bounded and naming
    what a question covers is how a learner finds it again.
    """

    id: uuid.UUID
    author_learner_id: uuid.UUID | None
    question_type: str
    source_type: str
    prompt: str
    options: tuple[AnswerOption, ...]
    expected_option_key: str
    explanation: str | None
    status: str
    written_at: datetime
    topics: tuple[PracticeTopic, ...] = ()


@dataclass(frozen=True, slots=True)
class QuestionPage:
    """One page of practice questions, with the total the pagination block reports."""

    questions: tuple[QuestionDetail, ...]
    total: int


@dataclass(frozen=True, slots=True)
class QuestionFilters:
    """What a caller may narrow a question list by.

    `topic_id` is what lets a learner see the practice they have written for one
    topic, at the API rather than by a client filtering a whole collection.
    """

    topic_id: uuid.UUID | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class NewQuestion:
    """A practice question a learner is asking to record (QZ-008).

    There is no `status` and no `source_type`: a question is written `ready` and
    `curated`, and setting it aside is a later statement made through QZ-010 —
    the shape RES-001 uses for a resource and PLN-004 for a plan item.

    Attributes:
        prompt: The question, in the learner's own words.
        option_texts: The options offered, in order. Keys are assigned by
            position by the domain rule, never accepted from a caller.
        correct_option_index: Which of `option_texts` is the expected answer,
            counted from zero.
        explanation: Why that answer is the expected one. Optional, and shown
            only once an attempt has been marked.
        topic_ids: The curriculum topics this question covers. **At least one is
            required**: a question linked to no topic could never be asked,
            because a quiz is assembled by topic.
    """

    prompt: str
    option_texts: tuple[str, ...]
    correct_option_index: int
    explanation: str | None = None
    topic_ids: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class QuestionChanges:
    """The field a question update asks to change (QZ-010).

    **`status` is the only one.** A question's prompt, options, expected answer,
    explanation, and topics are all fixed once written, because
    `quiz_attempt_answers` references the question by identifier: editing a
    prompt would silently rewrite the history of every attempt already marked
    against it. A learner corrects a question by retiring it and writing another,
    which keeps both readable — the position ADR-022 takes for a superseded plan.
    """

    status: str | None = None

    @property
    def is_empty(self) -> bool:
        """Whether the update asks for nothing at all."""
        return self.status is None


@dataclass(frozen=True, slots=True)
class QuizQuestionView:
    """One question as a quiz asks it: the prompt, the options, and nothing else.

    **Learner-safe.** There is deliberately no `expected_option_key` and no
    `explanation`, which is what QZ-002 means by "quiz content without expected
    answers": the answer is not sent to the browser before the learner has
    answered.
    """

    position: int
    question_id: uuid.UUID
    prompt: str
    options: tuple[AnswerOption, ...]


@dataclass(frozen=True, slots=True)
class QuizRecord:
    """One assembled checkpoint quiz, as stored."""

    id: uuid.UUID
    learner_id: uuid.UUID | None
    title: str
    source_type: str
    status: str


@dataclass(frozen=True, slots=True)
class QuizDetail:
    """One checkpoint quiz as a learner reads it, with its topics and its questions."""

    id: uuid.UUID
    learner_id: uuid.UUID | None
    title: str
    source_type: str
    status: str
    topics: tuple[PracticeTopic, ...] = ()
    questions: tuple[QuizQuestionView, ...] = ()


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    """One learner's attempt at a checkpoint quiz, as stored.

    Every timestamp is read from the server's clock, never accepted from a
    caller — the rule ADR-021 fixed for `plan_items.completed_at`.
    """

    id: uuid.UUID
    learner_id: uuid.UUID
    checkpoint_quiz_id: uuid.UUID
    status: str
    started_at: datetime | None
    submitted_at: datetime | None
    evaluated_at: datetime | None


@dataclass(frozen=True, slots=True)
class AttemptAnswerRecord:
    """What became of one question in one attempt, as stored.

    `chosen_option_key` and `is_correct` are both `None` for a question the
    learner left alone. **An unanswered question is not a wrong one.**
    """

    id: uuid.UUID
    quiz_attempt_id: uuid.UUID
    question_id: uuid.UUID
    chosen_option_key: str | None
    is_correct: bool | None


@dataclass(frozen=True, slots=True)
class AttemptOutcome:
    """One question of an attempt, as the learner reads it back.

    `expected_option_key` and `explanation` are `None` until the attempt has been
    marked, so an attempt still in progress never reveals its answers.

    There is **no mark and no marks available**: an outcome is `is_correct` —
    true, false, or `None` for unanswered — and nothing more.
    """

    position: int
    question_id: uuid.UUID
    prompt: str
    options: tuple[AnswerOption, ...]
    chosen_option_key: str | None
    expected_option_key: str | None
    explanation: str | None
    is_correct: bool | None


@dataclass(frozen=True, slots=True)
class AttemptDetail:
    """One attempt as a learner reads it, with what became of each question.

    `quiz_title` and `topics` are carried so a result reads on its own, without a
    second request to name the quiz it belongs to.

    **Nothing here totals the outcomes.** There is no score, no count of correct
    answers, and no percentage; the learner reads what happened question by
    question. See docs/domain/terminology.md and ADR-033.
    """

    id: uuid.UUID
    learner_id: uuid.UUID
    checkpoint_quiz_id: uuid.UUID
    quiz_title: str
    status: str
    started_at: datetime | None
    submitted_at: datetime | None
    evaluated_at: datetime | None
    topics: tuple[PracticeTopic, ...] = ()
    outcomes: tuple[AttemptOutcome, ...] = ()


@dataclass(frozen=True, slots=True)
class AttemptPage:
    """One page of the learner's attempts, with the total the pagination block reports."""

    attempts: tuple[AttemptDetail, ...]
    total: int


@dataclass(frozen=True, slots=True)
class NewQuiz:
    """A checkpoint quiz a learner is asking LearnFlow to assemble (QZ-001).

    Attributes:
        topic_ids: The topics to draw questions from. **At least one is
            required**, which is ADR-008's rule: a quiz covering no topic is
            invalid, and the request is rejected rather than stored.
    """

    topic_ids: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class AnswerSubmission:
    """One answer a learner is submitting (QZ-005).

    `option_key` is the key of the option chosen. A question the learner did not
    answer is simply absent from the submission rather than sent with a null.
    """

    question_id: uuid.UUID
    option_key: str
