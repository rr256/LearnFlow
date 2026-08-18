"""The persistence port the checkpoint-practice endpoints work through.

It reads and writes the learner's practice questions, the quizzes assembled from
them, the attempts made at those quizzes, and the curriculum rows needed to name
what each covers. Reading all of them through one port keeps a request to one
unit of work, for the reason `topic_progress_repository` records: assembling a
quiz writes a quiz, its topics, and its questions, and a learner must never end
up with a quiz that asks nothing.

Ordering is fixed here, for the reason `curriculum_repository` records — a page
cannot be ordered after it has been sliced. Questions and attempts are ordered
newest first, which is the order every other learner-owned collection uses. A
**quiz's own questions** are the exception: they are returned in `position`
order, because that order is the quiz, frozen when it was assembled by
`app.domain.checkpoint_marking.arrange_questions`.

Nothing here decides ownership, marks an answer, or chooses which questions a
quiz asks. Those are rules, and they live in the use case and the domain module.
"""

import uuid
from collections.abc import Mapping, Sequence
from typing import Protocol

from app.application.dto.checkpoint_practice import (
    AttemptAnswerRecord,
    AttemptRecord,
    PracticeTopic,
    QuestionFilters,
    QuestionRecord,
    QuizRecord,
)


class CheckpointPracticeRepository(Protocol):
    """Reads and writes a learner's practice questions, quizzes, and attempts."""

    # --- Curriculum ---------------------------------------------------------

    def list_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[PracticeTopic, ...]:
        """The topics named, in no particular order.

        Every identifier is asked for at once, so validating a link set stays one
        query. An identifier naming no stored topic is absent from the result,
        which is how the use case refuses a request that names one.
        """
        ...

    # --- Questions ----------------------------------------------------------

    def count_questions(self, *, learner_id: uuid.UUID, filters: QuestionFilters) -> int:
        """How many of this learner's questions match, for the pagination block."""
        ...

    def list_questions(
        self,
        *,
        learner_id: uuid.UUID,
        filters: QuestionFilters,
        limit: int,
        offset: int,
    ) -> tuple[QuestionRecord, ...]:
        """One page of the learner's practice questions, newest first."""
        ...

    def find_question(self, question_id: uuid.UUID) -> QuestionRecord | None:
        """The question with this identifier, or None.

        Ownership is a rule, so the use case decides it. This returns the record
        whoever wrote it, and the caller compares.
        """
        ...

    def add_question(self, record: QuestionRecord) -> None:
        """Store a new question. The caller owns the transaction."""
        ...

    def update_question(self, record: QuestionRecord) -> None:
        """Store a changed question. The caller owns the transaction."""
        ...

    def replace_question_topic_links(
        self, *, question_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]
    ) -> None:
        """Make these topics the question's links, removing any others.

        A replacement rather than a merge, as `replace_topic_links` is for a
        resource. Only a newly written question uses it today, because a
        question's topics are fixed once written.
        """
        ...

    def list_question_topic_links(
        self, question_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, tuple[uuid.UUID, ...]]:
        """The topic identifiers each question names, keyed by question.

        Every question on a page is asked for at once, so rendering a page stays
        one query rather than one per row. A question with no links is absent
        from the mapping rather than present with an empty tuple.
        """
        ...

    def list_askable_questions(
        self, *, learner_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]
    ) -> tuple[QuestionRecord, ...]:
        """The learner's `ready` questions linked to any of these topics.

        Exactly these topics, not their subtopics: a quiz asks what the learner
        linked to the topics they chose, which is a rule they can predict without
        knowing how the curriculum tree is shaped.

        A question linked to two of the chosen topics appears **once**.
        """
        ...

    # --- Quizzes ------------------------------------------------------------

    def add_quiz(self, record: QuizRecord) -> None:
        """Store a new checkpoint quiz. The caller owns the transaction."""
        ...

    def add_quiz_topics(self, *, quiz_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]) -> None:
        """Record the topics a quiz covers. At least one, per ADR-008."""
        ...

    def add_quiz_questions(self, *, quiz_id: uuid.UUID, question_ids: Sequence[uuid.UUID]) -> None:
        """Record the questions a quiz asks, in the order given.

        `position` counts from 1 and is the order the sequence arrives in, which
        the use case took from `arrange_questions`. It is an **order, not a
        score**.
        """
        ...

    def find_quiz(self, quiz_id: uuid.UUID) -> QuizRecord | None:
        """The quiz with this identifier, or None. Ownership is the caller's rule."""
        ...

    def list_quizzes(self, quiz_ids: Sequence[uuid.UUID]) -> tuple[QuizRecord, ...]:
        """The quizzes named, in no particular order.

        Asked for in one query so a page of attempts can be titled without one
        lookup per attempt.
        """
        ...

    def list_quiz_topics(
        self, quiz_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, tuple[uuid.UUID, ...]]:
        """The topic identifiers each quiz covers, keyed by quiz."""
        ...

    def list_quiz_questions(self, quiz_id: uuid.UUID) -> tuple[QuestionRecord, ...]:
        """The quiz's questions, in `position` order.

        Retired questions are included: a quiz asks what it was assembled with,
        and dropping a question the learner later set aside would change a quiz
        that attempts already reference.
        """
        ...

    # --- Attempts -----------------------------------------------------------

    def find_open_attempt(
        self, *, learner_id: uuid.UUID, quiz_id: uuid.UUID
    ) -> AttemptRecord | None:
        """This learner's unfinished attempt at this quiz, if one exists.

        What makes starting an attempt safe to ask for twice: a second request
        returns the first attempt rather than littering the learner's history —
        the position REV-004 takes for a review already waiting.
        """
        ...

    def add_attempt(self, record: AttemptRecord) -> None:
        """Store a new attempt. The caller owns the transaction."""
        ...

    def update_attempt(self, record: AttemptRecord) -> None:
        """Store a changed attempt. The caller owns the transaction."""
        ...

    def find_attempt(self, attempt_id: uuid.UUID) -> AttemptRecord | None:
        """The attempt with this identifier, or None. Ownership is the caller's rule."""
        ...

    def count_attempts(self, *, learner_id: uuid.UUID) -> int:
        """How many attempts this learner has made, for the pagination block."""
        ...

    def list_attempts(
        self, *, learner_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[AttemptRecord, ...]:
        """One page of the learner's attempts, newest first."""
        ...

    def replace_attempt_answers(
        self, *, attempt_id: uuid.UUID, answers: Sequence[AttemptAnswerRecord]
    ) -> None:
        """Make these the attempt's answers, removing any others.

        A replacement rather than a merge, so marking an attempt writes one
        consistent set. Submitting twice is refused by the use case, so this runs
        once per attempt today.
        """
        ...

    def list_attempt_answers(
        self, attempt_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, tuple[AttemptAnswerRecord, ...]]:
        """The answers of each attempt, keyed by attempt.

        Every attempt on a page is asked for at once, so rendering a page stays
        one query rather than one per row.
        """
        ...
