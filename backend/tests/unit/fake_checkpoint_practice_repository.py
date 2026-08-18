"""An in-memory stand-in for the checkpoint-practice repository port.

Questions and attempts are held in write order and returned newest first,
matching the order the port fixes and the SQLAlchemy adapter applies -- so a use
case relying on the store to sort fails here rather than passing by accident. A
quiz's questions come back in the order they were added, which is the `position`
order the adapter reads.

The controlled values are asserted on write, mirroring the database `CHECK`s: a
fake accepting a status PostgreSQL would refuse would let a use-case test pass on
a shape the real database cannot store.

The curriculum topics are supplied as a fixture rather than derived, because what
this fake stands in for is the *query*, and the rule being tested is what the use
case does with its answer.
"""

import uuid
from collections.abc import Mapping, Sequence

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
from app.infrastructure.persistence.assessment import (
    ATTEMPT_STATUSES,
    QUESTION_STATUSES,
    QUESTION_TYPES,
    QUIZ_STATUSES,
    SOURCE_TYPES,
)


class FakeCheckpointPracticeRepository:
    """Stores questions, quizzes, and attempts in lists, over fixed curriculum data."""

    def __init__(
        self,
        *,
        topics: Sequence[PracticeTopic] = (),
        questions: Sequence[QuestionRecord] = (),
        question_links: Mapping[uuid.UUID, Sequence[uuid.UUID]] | None = None,
    ) -> None:
        """Start from the topics that exist and any questions already written."""
        self.topics = list(topics)
        self.questions = list(questions)
        self.question_links: dict[uuid.UUID, tuple[uuid.UUID, ...]] = {
            question_id: tuple(topic_ids)
            for question_id, topic_ids in (question_links or {}).items()
        }
        self.quizzes: list[QuizRecord] = []
        self.quiz_topics: dict[uuid.UUID, tuple[uuid.UUID, ...]] = {}
        self.quiz_questions: dict[uuid.UUID, tuple[uuid.UUID, ...]] = {}
        self.attempts: list[AttemptRecord] = []
        self.attempt_answers: dict[uuid.UUID, tuple[AttemptAnswerRecord, ...]] = {}

    # --- Curriculum ---------------------------------------------------------

    def list_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[PracticeTopic, ...]:
        wanted = set(topic_ids)
        return tuple(topic for topic in self.topics if topic.id in wanted)

    # --- Questions ----------------------------------------------------------

    def count_questions(self, *, learner_id: uuid.UUID, filters: QuestionFilters) -> int:
        return len(self._matching_questions(learner_id, filters))

    def list_questions(
        self,
        *,
        learner_id: uuid.UUID,
        filters: QuestionFilters,
        limit: int,
        offset: int,
    ) -> tuple[QuestionRecord, ...]:
        return tuple(self._matching_questions(learner_id, filters)[offset : offset + limit])

    def find_question(self, question_id: uuid.UUID) -> QuestionRecord | None:
        return next((record for record in self.questions if record.id == question_id), None)

    def add_question(self, record: QuestionRecord) -> None:
        self._require_storable_question(record)
        if any(stored.id == record.id for stored in self.questions):
            raise AssertionError(f"Question {record.id} is already stored.")
        self.questions.append(record)

    def update_question(self, record: QuestionRecord) -> None:
        self._require_storable_question(record)
        for index, stored in enumerate(self.questions):
            if stored.id == record.id:
                self.questions[index] = record
                return
        raise LookupError(f"No practice question is stored with identifier {record.id}.")

    def replace_question_topic_links(
        self, *, question_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]
    ) -> None:
        if topic_ids:
            self.question_links[question_id] = tuple(topic_ids)
        else:
            self.question_links.pop(question_id, None)

    def list_question_topic_links(
        self, question_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, tuple[uuid.UUID, ...]]:
        wanted = set(question_ids)
        return {
            question_id: topic_ids
            for question_id, topic_ids in self.question_links.items()
            if question_id in wanted
        }

    def list_askable_questions(
        self, *, learner_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]
    ) -> tuple[QuestionRecord, ...]:
        chosen = set(topic_ids)
        return tuple(
            record
            for record in sorted(self.questions, key=lambda item: (item.written_at, item.id))
            if record.author_learner_id == learner_id
            and record.status == READY
            and chosen & set(self.question_links.get(record.id, ()))
        )

    # --- Quizzes ------------------------------------------------------------

    def add_quiz(self, record: QuizRecord) -> None:
        if record.status not in QUIZ_STATUSES:
            raise AssertionError(f"'{record.status}' is not a status a quiz may hold.")
        if record.source_type not in SOURCE_TYPES:
            raise AssertionError(f"'{record.source_type}' is not a source a quiz may hold.")
        self.quizzes.append(record)

    def add_quiz_topics(self, *, quiz_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]) -> None:
        if not topic_ids:
            raise AssertionError("ADR-008 requires a quiz to cover at least one topic.")
        self.quiz_topics[quiz_id] = tuple(topic_ids)

    def add_quiz_questions(self, *, quiz_id: uuid.UUID, question_ids: Sequence[uuid.UUID]) -> None:
        self.quiz_questions[quiz_id] = tuple(question_ids)

    def find_quiz(self, quiz_id: uuid.UUID) -> QuizRecord | None:
        return next((record for record in self.quizzes if record.id == quiz_id), None)

    def list_quizzes(self, quiz_ids: Sequence[uuid.UUID]) -> tuple[QuizRecord, ...]:
        wanted = set(quiz_ids)
        return tuple(record for record in self.quizzes if record.id in wanted)

    def list_quiz_topics(
        self, quiz_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, tuple[uuid.UUID, ...]]:
        wanted = set(quiz_ids)
        return {
            quiz_id: topic_ids
            for quiz_id, topic_ids in self.quiz_topics.items()
            if quiz_id in wanted
        }

    def list_quiz_questions(self, quiz_id: uuid.UUID) -> tuple[QuestionRecord, ...]:
        by_id = {record.id: record for record in self.questions}
        return tuple(
            by_id[question_id]
            for question_id in self.quiz_questions.get(quiz_id, ())
            if question_id in by_id
        )

    # --- Attempts -----------------------------------------------------------

    def find_open_attempt(
        self, *, learner_id: uuid.UUID, quiz_id: uuid.UUID
    ) -> AttemptRecord | None:
        return next(
            (
                record
                for record in reversed(self.attempts)
                if record.learner_id == learner_id
                and record.checkpoint_quiz_id == quiz_id
                and record.status == IN_PROGRESS
            ),
            None,
        )

    def add_attempt(self, record: AttemptRecord) -> None:
        self._require_storable_attempt(record)
        self.attempts.append(record)

    def update_attempt(self, record: AttemptRecord) -> None:
        self._require_storable_attempt(record)
        for index, stored in enumerate(self.attempts):
            if stored.id == record.id:
                self.attempts[index] = record
                return
        raise LookupError(f"No quiz attempt is stored with identifier {record.id}.")

    def find_attempt(self, attempt_id: uuid.UUID) -> AttemptRecord | None:
        return next((record for record in self.attempts if record.id == attempt_id), None)

    def count_attempts(self, *, learner_id: uuid.UUID) -> int:
        return len([record for record in self.attempts if record.learner_id == learner_id])

    def list_attempts(
        self, *, learner_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[AttemptRecord, ...]:
        newest_first = [
            record for record in reversed(self.attempts) if record.learner_id == learner_id
        ]
        return tuple(newest_first[offset : offset + limit])

    def replace_attempt_answers(
        self, *, attempt_id: uuid.UUID, answers: Sequence[AttemptAnswerRecord]
    ) -> None:
        question_ids = [answer.question_id for answer in answers]
        if len(set(question_ids)) != len(question_ids):
            raise AssertionError("One answer per question per attempt is a unique constraint.")
        self.attempt_answers[attempt_id] = tuple(answers)

    def list_attempt_answers(
        self, attempt_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, tuple[AttemptAnswerRecord, ...]]:
        wanted = set(attempt_ids)
        return {
            attempt_id: answers
            for attempt_id, answers in self.attempt_answers.items()
            if attempt_id in wanted
        }

    # --- Internals ----------------------------------------------------------

    def _matching_questions(
        self, learner_id: uuid.UUID, filters: QuestionFilters
    ) -> list[QuestionRecord]:
        """The learner's questions matching the filters, newest first."""
        matching = [
            record for record in reversed(self.questions) if record.author_learner_id == learner_id
        ]
        if filters.status is not None:
            matching = [record for record in matching if record.status == filters.status]
        if filters.topic_id is not None:
            matching = [
                record
                for record in matching
                if filters.topic_id in self.question_links.get(record.id, ())
            ]
        return matching

    def _require_storable_question(self, record: QuestionRecord) -> None:
        """Refuse a question PostgreSQL would refuse."""
        if record.question_type not in QUESTION_TYPES:
            raise AssertionError(f"'{record.question_type}' is not a stored question type.")
        if record.source_type not in SOURCE_TYPES:
            raise AssertionError(f"'{record.source_type}' is not a stored source type.")
        if record.status not in QUESTION_STATUSES:
            raise AssertionError(f"'{record.status}' is not a stored question status.")

    def _require_storable_attempt(self, record: AttemptRecord) -> None:
        """Refuse an attempt PostgreSQL would refuse."""
        if record.status not in ATTEMPT_STATUSES:
            raise AssertionError(f"'{record.status}' is not a stored attempt status.")
