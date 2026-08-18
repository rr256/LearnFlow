"""Persistence models for checkpoint practice: the questions, the quizzes, and the attempts.

Implements the *Assessment* schema area of docs/database/schema.md in full:

    checkpoint_quizzes <-> checkpoint_quiz_topics -> topics
    checkpoint_quizzes <-> quiz_questions -> questions <-> question_topic_links
    checkpoint_quizzes -> quiz_attempts -> quiz_attempt_answers

Unlike the two areas before it, this one arrives whole: every table it names is
created here, because a quiz that cannot be attempted and an attempt that cannot
be marked are not a smaller feature but a broken one. What is *not* created is a
set of columns, each absent for the reason ADR-011 gives -- nothing maintains it:

- ``questions.difficulty`` is an "optional controlled value" with no controlled
  vocabulary decided anywhere, and difficulty would rank one question above
  another, which nothing in LearnFlow does.
- ``quiz_questions.max_marks``, ``quiz_attempt_answers.awarded_marks``, and
  ``quiz_attempts.score`` / ``max_score`` are a mark scheme, and this build has
  none: a result states per-question outcomes and no total at all
  (docs/domain/terminology.md, ADR-033). Leaving them uncreated also leaves the
  one open detail docs/database/schema.md records -- numeric precision for score
  and marks columns -- undecided, rather than settling it in a change that would
  never read the answer.
- ``quiz_attempts.duration_seconds`` would need something to time an attempt.
  ``started_at`` and ``submitted_at`` already bound one, so storing the span
  between them would be a second source of truth for the same fact.
- ``quiz_attempt_answers.feedback`` would freeze the explanation an answer was
  marked with. It is unnecessary here because **a question is never edited**:
  it is retired and rewritten, so the explanation on the question cannot drift
  away from an attempt that was marked against it.

One column is created that docs/database/schema.md does not list:
``questions.author_learner_id``, nullable, mirroring ``resources.owner_learner_id``
exactly. The schema's own *Conventions* require ``learner_id`` on learner-owned
records, and every question here is written by the learner; nullable so the
curated or shared bank the table was designed for has somewhere to live later.
See ADR-033.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import (
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UuidPrimaryKeyMixin,
    in_clause,
)

QUESTION_TYPES = ("multiple_choice", "multiple_select", "numeric", "short_answer")
"""The forms an assessment item may take.

All four docs/database/schema.md documents, though **only ``multiple_choice`` is
written**. ``options`` and ``expected_answer`` are ``jsonb`` and already hold any
of the four, so what the other three wait on is a *marking rule* rather than
storage -- which makes offering one a use-case change rather than a migration,
the argument ADR-020 made for ``plan_items.status`` and ADR-032 for
``relationship_type``. ``short_answer`` additionally waits on a decision this
build deliberately does not make, because nothing here may mark free text.
"""

SOURCE_TYPES = ("generated", "verified_pyq", "curated")
"""Where a question or a quiz came from.

All three docs/database/schema.md documents, though **only ``curated`` is
written**: the learner writes their own questions and LearnFlow assembles them.
``generated`` waits on an AI provider, which does not exist; ``verified_pyq``
waits on verified previous-year content, which this repository deliberately does
not ship.
"""

QUESTION_STATUSES = ("draft", "ready", "retired")
"""The statuses ``questions.status`` accepts.

All three, though **``draft`` is never written**: a question is written whole in
one request, so nothing composes one over several. ``ready`` is a question a quiz
may ask; ``retired`` is one the learner has set aside, and it is **reversible** --
nothing here deletes a question, because attempts reference it.
"""

QUIZ_STATUSES = ("draft", "ready", "archived")
"""The statuses ``checkpoint_quizzes.status`` accepts.

All three, though **only ``ready`` is written**: a quiz is assembled complete or
refused. No endpoint changes a quiz's status, so neither ``draft`` nor
``archived`` is reachable yet.
"""

ATTEMPT_STATUSES = ("in_progress", "submitted", "evaluated", "abandoned")
"""The statuses ``quiz_attempts.status`` accepts.

All four, though **``in_progress`` and ``evaluated`` are the two written**.
Marking is synchronous and deterministic, so ``submitted`` is a state nothing
rests in; ``abandoned`` waits on something that would abandon an attempt, and an
unfinished attempt is simply left alone.
"""


class CheckpointQuiz(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """One assembled checkpoint quiz: a title, and the topics and questions it covers.

    ``learner_id`` is nullable as docs/database/schema.md approves, so a reusable
    quiz has somewhere to live later. **Nothing writes an ownerless quiz today**:
    the use case requires an owner on every write, because a row belonging to
    nobody would be invisible to every learner-scoped read.

    There is deliberately **no ``topic_id``**. ADR-008 fixes
    ``checkpoint_quiz_topics`` as the only quiz-to-topic link, so that a
    multi-topic checkpoint needs no migration later.
    """

    __tablename__ = "checkpoint_quizzes"

    learner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("learners.id"), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        CheckConstraint(in_clause("source_type", SOURCE_TYPES), name="source_type_is_known"),
        CheckConstraint(in_clause("status", QUIZ_STATUSES), name="status_is_known"),
    )


class CheckpointQuizTopic(CreatedAtMixin, Base):
    """A link between one checkpoint quiz and one curriculum topic.

    Write-once, so it carries ``created_at`` only, as ``resource_topic_links``
    does: a quiz's coverage is fixed when it is assembled.

    **At least one row per quiz is an application rule**, not a database one: no
    simple constraint expresses "at least one row in a child table", which is
    exactly what ADR-008 records and why the use case refuses a request naming no
    topic.
    """

    __tablename__ = "checkpoint_quiz_topics"

    checkpoint_quiz_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("checkpoint_quizzes.id"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"), primary_key=True)

    __table_args__ = (
        # The access pattern docs/database/schema.md lists under Required
        # Indexes: which quizzes cover a topic.
        Index(
            "ix_checkpoint_quiz_topics_topic_id_checkpoint_quiz_id",
            "topic_id",
            "checkpoint_quiz_id",
        ),
    )


class Question(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """One answerable prompt the learner wrote, with its options and its answer.

    ``options`` holds ``[{"key": "a", "text": ...}, ...]`` and ``expected_answer``
    holds ``{"option_key": "a"}``. Both are ``jsonb`` as docs/database/schema.md
    approves: the shape differs by question form, which is precisely the flexible
    payload the ``jsonb`` convention reserves it for.

    Keys are assigned by position by ``app.domain.checkpoint_marking``, never
    accepted from a caller, so a stored ``expected_answer`` always names an option
    the question actually offers.

    **A question is never edited.** A learner corrects one by retiring it and
    writing another, because ``quiz_attempt_answers`` references a question by
    identifier and rewriting a prompt would silently rewrite the history of every
    attempt already marked against it.
    """

    __tablename__ = "questions"

    author_learner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learners.id"), nullable=True
    )
    question_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB, nullable=True)
    expected_answer: Mapped[dict[str, str] | None] = mapped_column(JSONB, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        CheckConstraint(in_clause("question_type", QUESTION_TYPES), name="question_type_is_known"),
        CheckConstraint(in_clause("source_type", SOURCE_TYPES), name="source_type_is_known"),
        CheckConstraint(in_clause("status", QUESTION_STATUSES), name="status_is_known"),
        # Not in docs/database/schema.md's Required Indexes, and added because
        # this build's own access pattern needs it: assembling a quiz reads one
        # learner's questions that are ready to ask.
        Index("ix_questions_author_learner_id_status", "author_learner_id", "status"),
    )


class QuestionTopicLink(CreatedAtMixin, Base):
    """A link between one question and one curriculum topic.

    Write-once, as ``resource_topic_links`` is. A question may name **any** stored
    topic, including one that only groups subtopics, which follows ADR-032 rather
    than PRG-004: a question about the whole of Operating Systems is an ordinary
    thing to write, while a *stage* claiming understanding of a heading is not.
    """

    __tablename__ = "question_topic_links"

    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), primary_key=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"), primary_key=True)

    __table_args__ = (
        # How a quiz finds the questions covering the topics a learner chose.
        Index("ix_question_topic_links_topic_id_question_id", "topic_id", "question_id"),
    )


class QuizQuestion(CreatedAtMixin, Base):
    """One question's place in one checkpoint quiz.

    ``position`` is an **order, not a score** -- the distinction
    ``plan_items.priority`` draws. It records the order
    ``arrange_questions`` put the questions in, which is the order they were
    written, and it is frozen here so a quiz asks the same questions in the same
    order however many times it is opened.

    ``max_marks`` is deliberately not created; see the module docstring.
    """

    __tablename__ = "quiz_questions"

    checkpoint_quiz_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("checkpoint_quizzes.id"), primary_key=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("position >= 1", name="position_is_positive"),
        # docs/database/schema.md: no two questions share a place in one quiz.
        UniqueConstraint("checkpoint_quiz_id", "position"),
    )


class QuizAttempt(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """One learner's attempt at one checkpoint quiz.

    ``started_at`` is written when the attempt begins and ``submitted_at`` and
    ``evaluated_at`` when it is marked. Marking is synchronous, so the latter two
    coincide today; both are kept because they answer different questions, and a
    marking step that ever becomes asynchronous would separate them without a
    migration.

    Every timestamp is read from the server's clock rather than accepted from a
    caller, the rule ADR-021 fixed for ``plan_items.completed_at``.

    There is deliberately **no score and no duration**; see the module docstring.
    """

    __tablename__ = "quiz_attempts"

    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)
    checkpoint_quiz_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("checkpoint_quizzes.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(in_clause("status", ATTEMPT_STATUSES), name="status_is_known"),
        # The access pattern docs/database/schema.md lists under Required
        # Indexes: one learner's attempts at a quiz, newest first.
        Index(
            "ix_quiz_attempts_learner_id_checkpoint_quiz_id_created_at",
            "learner_id",
            "checkpoint_quiz_id",
            "created_at",
        ),
    )


class QuizAttemptAnswer(UuidPrimaryKeyMixin, TimestampMixin, Base):
    """What became of one question in one attempt.

    ``submitted_answer`` holds ``{"option_key": "c"}`` or is NULL when the learner
    left the question alone, and ``is_correct`` is NULL alongside it. **An
    unanswered question is not a wrong one**, which is the distinction the
    nullable column exists to keep: writing ``false`` there would state something
    about the learner that they did not.

    ``awarded_marks`` and ``feedback`` are deliberately not created; see the
    module docstring.
    """

    __tablename__ = "quiz_attempt_answers"

    quiz_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_attempts.id"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), nullable=False)
    submitted_answer: Mapped[dict[str, str] | None] = mapped_column(JSONB, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(nullable=True)

    __table_args__ = (
        # docs/database/schema.md: one answer per question per attempt. Submitting
        # twice is refused by the use case, and refused again here.
        UniqueConstraint("quiz_attempt_id", "question_id"),
    )
