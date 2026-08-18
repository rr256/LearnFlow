"""SQLAlchemy implementation of the checkpoint-practice repository port.

Serves QZ-001 to QZ-010. It maps rows to the application's plain records and
back, writes a quiz with its topics and its questions, and reads the curriculum
rows that name what each covers.

It decides nothing. Which question forms may be written, whether a question
belongs to the effective learner, which questions a quiz asks, and how an answer
is marked are all settled by the use case and the domain rule
(docs/architecture/dependency-rules.md).

The `jsonb` payloads on `questions` and `quiz_attempt_answers` are read and
written **only here**. `QuestionRecord` carries flat `options` and
`expected_option_key`, so no layer above persistence knows the stored shape.

The session's transaction is owned by the caller. Nothing here commits.
"""

import uuid
from collections.abc import Mapping, Sequence

from sqlalchemy import ColumnElement, Select, delete, func, select
from sqlalchemy.orm import Session

from app.application.dto.checkpoint_practice import (
    IN_PROGRESS,
    READY,
    AttemptAnswerRecord,
    AttemptRecord,
    PracticeTopic,
    QuestionFilters,
    QuestionRecord,
    QuizRecord,
)
from app.domain.checkpoint_marking import AnswerOption
from app.infrastructure.persistence.assessment import (
    CheckpointQuiz,
    CheckpointQuizTopic,
    Question,
    QuestionTopicLink,
    QuizAttempt,
    QuizAttemptAnswer,
    QuizQuestion,
)
from app.infrastructure.persistence.curriculum import Subject, Topic

OPTION_KEY = "option_key"
"""The single member of a stored answer payload.

`expected_answer` and `submitted_answer` are both `{"option_key": "a"}`. Named
once here so the two cannot drift apart over a typo, and confined to this module
so the rest of the application never sees the payload.
"""


class SqlAlchemyCheckpointPracticeRepository:
    """Reads and writes practice questions, quizzes, and attempts through a session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one unit of work."""
        self._session = session

    # --- Curriculum ---------------------------------------------------------

    def list_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[PracticeTopic, ...]:
        """The topics named, in no particular order."""
        if not topic_ids:
            return ()
        rows = self._session.execute(
            select(Topic.id, Topic.code, Topic.name, Subject.id, Subject.name)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(Topic.id.in_(set(topic_ids)))
        ).all()
        return tuple(
            PracticeTopic(
                id=row[0], code=row[1], name=row[2], subject_id=row[3], subject_name=row[4]
            )
            for row in rows
        )

    # --- Questions ----------------------------------------------------------

    def count_questions(self, *, learner_id: uuid.UUID, filters: QuestionFilters) -> int:
        """How many of this learner's questions match, ignoring any page window."""
        total = self._session.scalar(
            select(func.count())
            .select_from(Question)
            .where(*_question_filters(learner_id, filters))
            .where(*_question_topic_condition(filters))
        )
        return int(total or 0)

    def list_questions(
        self,
        *,
        learner_id: uuid.UUID,
        filters: QuestionFilters,
        limit: int,
        offset: int,
    ) -> tuple[QuestionRecord, ...]:
        """One page of the learner's practice questions, newest first."""
        rows = self._session.scalars(
            _newest_questions_first(
                select(Question)
                .where(*_question_filters(learner_id, filters))
                .where(*_question_topic_condition(filters))
            )
            .limit(limit)
            .offset(offset)
        ).all()
        return tuple(_question_record(row) for row in rows)

    def find_question(self, question_id: uuid.UUID) -> QuestionRecord | None:
        """The question with this identifier, or None."""
        row = self._session.get(Question, question_id)
        return None if row is None else _question_record(row)

    def add_question(self, record: QuestionRecord) -> None:
        """Store a new question.

        `created_at` is written from the record rather than left to the column's
        server default, because `written_at` is what a quiz is ordered by: taking
        it from the use case's clock keeps the order testable and keeps one
        instant describing the row.
        """
        self._session.add(
            Question(
                id=record.id,
                author_learner_id=record.author_learner_id,
                question_type=record.question_type,
                source_type=record.source_type,
                prompt=record.prompt,
                options=[{"key": option.key, "text": option.text} for option in record.options],
                expected_answer={OPTION_KEY: record.expected_option_key},
                explanation=record.explanation,
                status=record.status,
                created_at=record.written_at,
                updated_at=record.written_at,
            )
        )

    def update_question(self, record: QuestionRecord) -> None:
        """Store a changed question.

        Only `status` may differ; see `QuestionChanges`. The prompt, options,
        expected answer, and explanation are written back unchanged rather than
        left out, so this mapping stays complete if that rule is ever revisited.

        Raises:
            LookupError: The question is not stored. The use case has already
                established that it is, so reaching this means the row vanished
                between the read and the write.
        """
        row = self._session.get(Question, record.id)
        if row is None:
            raise LookupError(f"No practice question is stored with identifier {record.id}.")
        row.status = record.status

    def replace_question_topic_links(
        self, *, question_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]
    ) -> None:
        """Make these topics the question's links, removing any others."""
        self._session.execute(
            delete(QuestionTopicLink).where(QuestionTopicLink.question_id == question_id)
        )
        # Flushed before the inserts so a replaced set cannot collide with the
        # composite primary key of the rows being removed in the same batch.
        self._session.flush()
        for topic_id in topic_ids:
            self._session.add(QuestionTopicLink(question_id=question_id, topic_id=topic_id))

    def list_question_topic_links(
        self, question_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, tuple[uuid.UUID, ...]]:
        """The topic identifiers each question names, keyed by question."""
        if not question_ids:
            return {}
        rows = self._session.execute(
            select(QuestionTopicLink.question_id, QuestionTopicLink.topic_id)
            .where(QuestionTopicLink.question_id.in_(question_ids))
            # Ordered so a question's topics read the same way on every request;
            # the composite key alone leaves the order to the database.
            .order_by(
                QuestionTopicLink.question_id,
                QuestionTopicLink.created_at,
                QuestionTopicLink.topic_id,
            )
        ).all()

        links: dict[uuid.UUID, tuple[uuid.UUID, ...]] = {}
        for question_id, topic_id in rows:
            links[question_id] = (*links.get(question_id, ()), topic_id)
        return links

    def list_askable_questions(
        self, *, learner_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]
    ) -> tuple[QuestionRecord, ...]:
        """The learner's `ready` questions linked to any of these topics.

        An `EXISTS` rather than a join, so a question covering two of the chosen
        topics is returned once. A join would repeat it and the quiz would ask it
        twice.
        """
        if not topic_ids:
            return ()
        covers_a_chosen_topic = (
            select(QuestionTopicLink.question_id)
            .where(
                QuestionTopicLink.question_id == Question.id,
                QuestionTopicLink.topic_id.in_(set(topic_ids)),
            )
            .exists()
        )
        rows = self._session.scalars(
            select(Question)
            .where(
                Question.author_learner_id == learner_id,
                Question.status == READY,
                covers_a_chosen_topic,
            )
            # Ordered here too, although `arrange_questions` decides the quiz's
            # order: an unordered read makes the same request return rows in
            # different orders, which would make a test pass or fail by chance.
            .order_by(Question.created_at, Question.id)
        ).all()
        return tuple(_question_record(row) for row in rows)

    # --- Quizzes ------------------------------------------------------------

    def add_quiz(self, record: QuizRecord) -> None:
        """Store a new checkpoint quiz."""
        self._session.add(
            CheckpointQuiz(
                id=record.id,
                learner_id=record.learner_id,
                title=record.title,
                source_type=record.source_type,
                status=record.status,
            )
        )

    def add_quiz_topics(self, *, quiz_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]) -> None:
        """Record the topics a quiz covers."""
        for topic_id in topic_ids:
            self._session.add(CheckpointQuizTopic(checkpoint_quiz_id=quiz_id, topic_id=topic_id))

    def add_quiz_questions(self, *, quiz_id: uuid.UUID, question_ids: Sequence[uuid.UUID]) -> None:
        """Record the questions a quiz asks, in the order given."""
        for position, question_id in enumerate(question_ids, start=1):
            self._session.add(
                QuizQuestion(checkpoint_quiz_id=quiz_id, question_id=question_id, position=position)
            )

    def find_quiz(self, quiz_id: uuid.UUID) -> QuizRecord | None:
        """The quiz with this identifier, or None."""
        row = self._session.get(CheckpointQuiz, quiz_id)
        return None if row is None else _quiz_record(row)

    def list_quizzes(self, quiz_ids: Sequence[uuid.UUID]) -> tuple[QuizRecord, ...]:
        """The quizzes named, in no particular order."""
        if not quiz_ids:
            return ()
        rows = self._session.scalars(
            select(CheckpointQuiz).where(CheckpointQuiz.id.in_(set(quiz_ids)))
        ).all()
        return tuple(_quiz_record(row) for row in rows)

    def list_quiz_topics(
        self, quiz_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, tuple[uuid.UUID, ...]]:
        """The topic identifiers each quiz covers, keyed by quiz."""
        if not quiz_ids:
            return {}
        rows = self._session.execute(
            select(CheckpointQuizTopic.checkpoint_quiz_id, CheckpointQuizTopic.topic_id)
            .where(CheckpointQuizTopic.checkpoint_quiz_id.in_(set(quiz_ids)))
            .order_by(
                CheckpointQuizTopic.checkpoint_quiz_id,
                CheckpointQuizTopic.created_at,
                CheckpointQuizTopic.topic_id,
            )
        ).all()

        links: dict[uuid.UUID, tuple[uuid.UUID, ...]] = {}
        for quiz_id, topic_id in rows:
            links[quiz_id] = (*links.get(quiz_id, ()), topic_id)
        return links

    def list_quiz_questions(self, quiz_id: uuid.UUID) -> tuple[QuestionRecord, ...]:
        """The quiz's questions, in `position` order.

        No status filter: a quiz asks what it was assembled with, so a question
        the learner has since retired still appears. Dropping it would change a
        quiz that attempts already reference.
        """
        rows = self._session.scalars(
            select(Question)
            .join(QuizQuestion, QuizQuestion.question_id == Question.id)
            .where(QuizQuestion.checkpoint_quiz_id == quiz_id)
            .order_by(QuizQuestion.position)
        ).all()
        return tuple(_question_record(row) for row in rows)

    # --- Attempts -----------------------------------------------------------

    def find_open_attempt(
        self, *, learner_id: uuid.UUID, quiz_id: uuid.UUID
    ) -> AttemptRecord | None:
        """This learner's unfinished attempt at this quiz, if one exists."""
        row = self._session.scalars(
            select(QuizAttempt)
            .where(
                QuizAttempt.learner_id == learner_id,
                QuizAttempt.checkpoint_quiz_id == quiz_id,
                QuizAttempt.status == IN_PROGRESS,
            )
            .order_by(QuizAttempt.created_at.desc(), QuizAttempt.id)
            .limit(1)
        ).first()
        return None if row is None else _attempt_record(row)

    def add_attempt(self, record: AttemptRecord) -> None:
        """Store a new attempt."""
        self._session.add(
            QuizAttempt(
                id=record.id,
                learner_id=record.learner_id,
                checkpoint_quiz_id=record.checkpoint_quiz_id,
                status=record.status,
                started_at=record.started_at,
                submitted_at=record.submitted_at,
                evaluated_at=record.evaluated_at,
            )
        )

    def update_attempt(self, record: AttemptRecord) -> None:
        """Store a changed attempt.

        Raises:
            LookupError: The attempt is not stored.
        """
        row = self._session.get(QuizAttempt, record.id)
        if row is None:
            raise LookupError(f"No quiz attempt is stored with identifier {record.id}.")
        row.status = record.status
        row.started_at = record.started_at
        row.submitted_at = record.submitted_at
        row.evaluated_at = record.evaluated_at

    def find_attempt(self, attempt_id: uuid.UUID) -> AttemptRecord | None:
        """The attempt with this identifier, or None."""
        row = self._session.get(QuizAttempt, attempt_id)
        return None if row is None else _attempt_record(row)

    def count_attempts(self, *, learner_id: uuid.UUID) -> int:
        """How many attempts this learner has made."""
        total = self._session.scalar(
            select(func.count())
            .select_from(QuizAttempt)
            .where(QuizAttempt.learner_id == learner_id)
        )
        return int(total or 0)

    def list_attempts(
        self, *, learner_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[AttemptRecord, ...]:
        """One page of the learner's attempts, newest first."""
        rows = self._session.scalars(
            select(QuizAttempt)
            .where(QuizAttempt.learner_id == learner_id)
            .order_by(QuizAttempt.created_at.desc(), QuizAttempt.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return tuple(_attempt_record(row) for row in rows)

    def replace_attempt_answers(
        self, *, attempt_id: uuid.UUID, answers: Sequence[AttemptAnswerRecord]
    ) -> None:
        """Make these the attempt's answers, removing any others."""
        self._session.execute(
            delete(QuizAttemptAnswer).where(QuizAttemptAnswer.quiz_attempt_id == attempt_id)
        )
        # Flushed before the inserts so a rewritten set cannot collide with the
        # unique `(quiz_attempt_id, question_id)` constraint on the rows being
        # removed in the same batch.
        self._session.flush()
        for answer in answers:
            self._session.add(
                QuizAttemptAnswer(
                    id=answer.id,
                    quiz_attempt_id=answer.quiz_attempt_id,
                    question_id=answer.question_id,
                    submitted_answer=(
                        None
                        if answer.chosen_option_key is None
                        else {OPTION_KEY: answer.chosen_option_key}
                    ),
                    is_correct=answer.is_correct,
                )
            )

    def list_attempt_answers(
        self, attempt_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, tuple[AttemptAnswerRecord, ...]]:
        """The answers of each attempt, keyed by attempt."""
        if not attempt_ids:
            return {}
        rows = self._session.scalars(
            select(QuizAttemptAnswer)
            .where(QuizAttemptAnswer.quiz_attempt_id.in_(set(attempt_ids)))
            .order_by(QuizAttemptAnswer.quiz_attempt_id, QuizAttemptAnswer.created_at)
        ).all()

        answers: dict[uuid.UUID, tuple[AttemptAnswerRecord, ...]] = {}
        for row in rows:
            record = _answer_record(row)
            answers[row.quiz_attempt_id] = (*answers.get(row.quiz_attempt_id, ()), record)
        return answers


def _question_filters(
    learner_id: uuid.UUID, filters: QuestionFilters
) -> tuple[ColumnElement[bool], ...]:
    """The conditions a listed question must meet, other than its topic.

    No status is assumed, which is how RES-002, PLN-002, and REV-001 treat their
    own: a caller wanting only what a quiz may ask asks for `ready`.
    """
    conditions: list[ColumnElement[bool]] = [Question.author_learner_id == learner_id]
    if filters.status is not None:
        conditions.append(Question.status == filters.status)
    return tuple(conditions)


def _question_topic_condition(filters: QuestionFilters) -> tuple[ColumnElement[bool], ...]:
    """Restrict to questions linked to one topic, when one was asked for.

    An `EXISTS` rather than a join, for the reason `list_askable_questions`
    gives: a question covering a topic appears once however many links it holds.
    """
    if filters.topic_id is None:
        return ()
    return (
        select(QuestionTopicLink.question_id)
        .where(
            QuestionTopicLink.question_id == Question.id,
            QuestionTopicLink.topic_id == filters.topic_id,
        )
        .exists(),
    )


def _newest_questions_first(statement: Select[tuple[Question]]) -> Select[tuple[Question]]:
    """Newest first, then by identifier.

    The order every learner-owned collection uses. The identifier breaks a tie
    two questions written in the same instant would otherwise leave to the
    database, which would let one page repeat or omit a record.
    """
    return statement.order_by(Question.created_at.desc(), Question.id)


def _question_record(row: Question) -> QuestionRecord:
    """Map a stored question onto the application's plain record.

    The `jsonb` payloads are flattened here and nowhere else. A row whose
    payloads are missing or malformed reads back with no options and an empty
    expected key rather than raising: nothing writes such a row, and a read that
    crashed would take a whole page down with it.
    """
    options = tuple(
        AnswerOption(key=str(option.get("key", "")), text=str(option.get("text", "")))
        for option in (row.options or [])
    )
    expected = row.expected_answer or {}
    return QuestionRecord(
        id=row.id,
        author_learner_id=row.author_learner_id,
        question_type=row.question_type,
        source_type=row.source_type,
        prompt=row.prompt,
        options=options,
        expected_option_key=str(expected.get(OPTION_KEY, "")),
        explanation=row.explanation,
        status=row.status,
        written_at=row.created_at,
    )


def _quiz_record(row: CheckpointQuiz) -> QuizRecord:
    """Map a stored quiz onto the application's plain record."""
    return QuizRecord(
        id=row.id,
        learner_id=row.learner_id,
        title=row.title,
        source_type=row.source_type,
        status=row.status,
    )


def _attempt_record(row: QuizAttempt) -> AttemptRecord:
    """Map a stored attempt onto the application's plain record."""
    return AttemptRecord(
        id=row.id,
        learner_id=row.learner_id,
        checkpoint_quiz_id=row.checkpoint_quiz_id,
        status=row.status,
        started_at=row.started_at,
        submitted_at=row.submitted_at,
        evaluated_at=row.evaluated_at,
    )


def _answer_record(row: QuizAttemptAnswer) -> AttemptAnswerRecord:
    """Map a stored answer onto the application's plain record."""
    submitted = row.submitted_answer or {}
    chosen = submitted.get(OPTION_KEY)
    return AttemptAnswerRecord(
        id=row.id,
        quiz_attempt_id=row.quiz_attempt_id,
        question_id=row.question_id,
        chosen_option_key=None if chosen is None else str(chosen),
        is_correct=row.is_correct,
    )
