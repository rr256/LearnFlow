"""Assembling a checkpoint quiz, attempting it, and reading back what happened.

Serves QZ-001, QZ-002, QZ-003, QZ-005, QZ-006, and QZ-007, which complete the
workflow the question bank in `manage_practice_questions` supplies. Together they
begin [FR-009](../../../docs/requirements/functional.md#fr-009-topic-checkpoint-practice).

**Deterministic, with no AI provider.** A quiz is assembled by
`app.domain.checkpoint_marking`, whose rules are pure functions: the same
questions produce the same quiz, in the same order, and the same answers are
marked the same way. Nothing is generated, sampled, randomised, or retrieved —
which is the promise ADR-020 made for a study plan, kept here for an assessment.

**A quiz asks every question the learner wrote for the topics they chose.**
LearnFlow does not select some and leave others out: choosing which few to ask
would be a ranking, and nothing in LearnFlow ranks. The learner decides how long
a quiz is by how many topics they pick and how many questions they have written.

**The result carries no score.** There is no total, no mark, no count of correct
answers, and no percentage — the learner reads what became of each question, one
at a time. `quiz_attempts.score` and the marks columns are not created at all.
See docs/domain/terminology.md and ADR-033.

**An unanswered question is not a wrong one**, and a result says so.

**Nothing else moves.** Assembling, attempting, or marking a quiz writes no
learning stage, no plan, no plan item, and no revision. A checkpoint says what
happened in one attempt; it does not claim a topic is understood, which is the
rule FR-005 and FR-009 both state and which nothing here may quietly break.
"""

import uuid
from collections.abc import Mapping, Sequence

from app.application.dto.checkpoint_practice import (
    CURATED,
    EVALUATED,
    IN_PROGRESS,
    MAX_QUIZ_TOPICS,
    READY,
    AnswerSubmission,
    AttemptAnswerRecord,
    AttemptDetail,
    AttemptOutcome,
    AttemptPage,
    AttemptRecord,
    NewQuiz,
    PracticeTopic,
    QuestionRecord,
    QuizDetail,
    QuizQuestionView,
    QuizRecord,
)
from app.application.ports.checkpoint_practice_repository import CheckpointPracticeRepository
from app.application.ports.clock import Clock
from app.application.ports.learner_repository import LearnerRecord, LearnerRepository
from app.application.use_cases.local_learner import resolve_local_learner
from app.domain.checkpoint_marking import (
    AskableQuestion,
    SubmittedAnswer,
    arrange_questions,
    mark_attempt,
)


class CheckpointQuizError(Exception):
    """Base class for the refusals this use case makes."""


class LearnerNotSetUpError(CheckpointQuizError):
    """No learner is stored, so no quiz can be assembled or attempted."""


class QuizNotFoundError(CheckpointQuizError):
    """No such quiz is stored, or it belongs to another learner."""


class AttemptNotFoundError(CheckpointQuizError):
    """No such attempt is stored, or it belongs to another learner."""


class MissingQuizTopicError(CheckpointQuizError):
    """A quiz request naming no topic.

    ADR-008's rule: a quiz covers one or more topics, and one covering none is
    invalid. No database constraint can express "at least one row in a child
    table", so it is refused here.
    """


class UnknownTopicError(CheckpointQuizError):
    """A topic identifier naming nothing stored."""


class DuplicateQuizTopicError(CheckpointQuizError):
    """The same topic named more than once in one request."""


class TooManyQuizTopicsError(CheckpointQuizError):
    """More topics named than one request may cover."""


class NoQuestionsForTopicsError(CheckpointQuizError):
    """The learner has written no ready questions for the chosen topics.

    Refused rather than stored: a quiz that asks nothing cannot be attempted, and
    writing one would leave the learner with an empty record and no explanation.
    """


class AttemptAlreadyMarkedError(CheckpointQuizError):
    """An attempt that has already been submitted and marked.

    A second submission is refused rather than allowed to overwrite the first,
    which is the position PLN-004 takes for an item on a superseded plan: a
    record of what happened is not edited after the fact. The learner starts a
    new attempt instead, and both stay readable.
    """


class UnknownQuestionError(CheckpointQuizError):
    """A submitted answer naming a question this quiz does not ask."""


class DuplicateAnswerError(CheckpointQuizError):
    """The same question answered more than once in one submission."""


class UnknownOptionError(CheckpointQuizError):
    """A submitted answer naming an option the question does not offer."""


class ManageCheckpointQuizzes:
    """Assembles checkpoint quizzes, runs attempts at them, and reads results back."""

    def __init__(
        self,
        *,
        learners: LearnerRepository,
        practice: CheckpointPracticeRepository,
        clock: Clock,
    ) -> None:
        """Bind the use case to its ports."""
        self._learners = learners
        self._practice = practice
        self._clock = clock

    def assemble(self, request: NewQuiz) -> QuizDetail:
        """Assemble a checkpoint quiz from the learner's questions for these topics.

        The caller owns the transaction: this writes the quiz, its topics, and its
        questions, and never commits. All three are one unit of work, so a learner
        cannot end up with a quiz covering topics it asks nothing about.

        **Every ready question linked to a chosen topic is asked**, in the order
        the questions were written, which `arrange_questions` decides. A question
        linked to two chosen topics is asked once. A **retired** question is left
        out, which is what retiring one means.

        Asking again assembles a **new** quiz rather than returning the last one:
        the learner may have written more questions since, and a quiz is the
        record of what was asked on one occasion. Nothing is superseded and
        nothing is deleted.

        Raises:
            LearnerNotSetUpError: No learner exists to own the quiz.
            AmbiguousLocalLearnerError: More than one learner is stored.
            MissingQuizTopicError: No topic was named.
            UnknownTopicError: A topic identifier names nothing stored.
            DuplicateQuizTopicError: A topic was named more than once.
            TooManyQuizTopicsError: More topics than one request may cover.
            NoQuestionsForTopicsError: No ready question covers those topics.
        """
        learner = self._require_learner()
        topics = self._validated_topics(request.topic_ids)

        candidates = self._practice.list_askable_questions(
            learner_id=learner.id, topic_ids=[topic.id for topic in topics]
        )
        if not candidates:
            raise NoQuestionsForTopicsError(
                "You have not written any practice questions for those topics yet. "
                "Write one first, then ask for a quiz."
            )

        order = arrange_questions(
            AskableQuestion(
                id=question.id,
                written_at=question.written_at,
                expected_option_key=question.expected_option_key,
            )
            for question in candidates
        )

        quiz = QuizRecord(
            id=uuid.uuid4(),
            learner_id=learner.id,
            title=_title_for(topics),
            # The questions are the learner's own, so the quiz is curated too.
            source_type=CURATED,
            # A quiz is assembled complete or refused, so it is never a draft.
            status=READY,
        )
        self._practice.add_quiz(quiz)
        self._practice.add_quiz_topics(quiz_id=quiz.id, topic_ids=[topic.id for topic in topics])
        self._practice.add_quiz_questions(quiz_id=quiz.id, question_ids=order)

        by_id = {question.id: question for question in candidates}
        return QuizDetail(
            id=quiz.id,
            learner_id=quiz.learner_id,
            title=quiz.title,
            source_type=quiz.source_type,
            status=quiz.status,
            topics=topics,
            questions=_asked(tuple(by_id[question_id] for question_id in order)),
        )

    def read_quiz(self, quiz_id: uuid.UUID) -> QuizDetail:
        """One of the learner's quizzes, with the questions it asks.

        **Learner-safe.** The expected answers and explanations are not included;
        `QuizQuestionView` has nowhere to put them. That is what QZ-002 means by
        "quiz content without expected answers", and it is enforced by the shape
        rather than by remembering to strip a field.

        Raises:
            QuizNotFoundError: No such quiz, or it belongs to another learner.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        quiz = self._require_own_quiz(quiz_id)
        return QuizDetail(
            id=quiz.id,
            learner_id=quiz.learner_id,
            title=quiz.title,
            source_type=quiz.source_type,
            status=quiz.status,
            topics=self._quiz_topics([quiz.id]).get(quiz.id, ()),
            questions=_asked(self._practice.list_quiz_questions(quiz.id)),
        )

    def start_attempt(self, quiz_id: uuid.UUID) -> tuple[AttemptDetail, bool]:
        """Begin an attempt at one of the learner's quizzes.

        The caller owns the transaction.

        **Asking twice starts nothing the second time.** An unfinished attempt at
        the same quiz is returned instead, which is the position REV-004 takes for
        a review already waiting: a learner who reloads the page or submits a form
        twice should not accumulate abandoned records they never asked for.

        Raises:
            QuizNotFoundError: No such quiz, or it belongs to another learner.
            LearnerNotSetUpError: No learner exists to own the attempt.
            AmbiguousLocalLearnerError: More than one learner is stored.

        Returns:
            The attempt, and whether it was created by this request.
        """
        learner = self._require_learner()
        quiz = self._require_own_quiz(quiz_id)

        existing = self._practice.find_open_attempt(learner_id=learner.id, quiz_id=quiz.id)
        if existing is not None:
            return self._describe_attempts([existing])[0], False

        # Read once and reused, so `created_at` and `started_at` cannot describe
        # two different instants for the same record.
        now = self._clock.now()
        attempt = AttemptRecord(
            id=uuid.uuid4(),
            learner_id=learner.id,
            checkpoint_quiz_id=quiz.id,
            status=IN_PROGRESS,
            started_at=now,
            submitted_at=None,
            evaluated_at=None,
        )
        self._practice.add_attempt(attempt)
        return self._describe_attempts([attempt])[0], True

    def submit(self, attempt_id: uuid.UUID, answers: Sequence[AnswerSubmission]) -> AttemptDetail:
        """Submit an attempt's answers and mark them, in one request.

        The caller owns the transaction.

        **The whole attempt is submitted at once.** QZ-004, which saves one answer
        before submission, is deliberately not implemented: a single submission is
        one form post that works with no JavaScript, and saving answers one at a
        time needs a client this build does not have. See ADR-033.

        A question the submission leaves out is recorded as **unanswered** —
        `submitted_answer` and `is_correct` both null — never as wrong.

        Marking is `app.domain.checkpoint_marking.mark_attempt`: pure, and the
        same answers always produce the same outcome.

        Raises:
            AttemptNotFoundError: No such attempt, or it is not the learner's.
            AttemptAlreadyMarkedError: The attempt has already been marked.
            UnknownQuestionError: An answer names a question the quiz does not ask.
            DuplicateAnswerError: A question is answered more than once.
            UnknownOptionError: An answer names an option the question lacks.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        attempt = self._require_own_attempt(attempt_id)
        if attempt.status == EVALUATED:
            raise AttemptAlreadyMarkedError(
                f"Attempt {attempt_id} has already been submitted and marked. "
                "Start a new attempt to answer these questions again."
            )

        questions = self._practice.list_quiz_questions(attempt.checkpoint_quiz_id)
        submitted = _validated_answers(answers, questions)

        marked = mark_attempt(
            [
                AskableQuestion(
                    id=question.id,
                    written_at=question.written_at,
                    expected_option_key=question.expected_option_key,
                )
                for question in questions
            ],
            submitted,
        )
        self._practice.replace_attempt_answers(
            attempt_id=attempt.id,
            answers=[
                AttemptAnswerRecord(
                    id=uuid.uuid4(),
                    quiz_attempt_id=attempt.id,
                    question_id=answer.question_id,
                    chosen_option_key=answer.chosen_option_key,
                    is_correct=answer.is_correct,
                )
                for answer in marked
            ],
        )

        # Marking is synchronous, so submission and evaluation are one instant.
        # Both are stored because they answer different questions, and a marking
        # step that ever becomes asynchronous would separate them without a
        # migration.
        now = self._clock.now()
        evaluated = AttemptRecord(
            id=attempt.id,
            learner_id=attempt.learner_id,
            checkpoint_quiz_id=attempt.checkpoint_quiz_id,
            status=EVALUATED,
            started_at=attempt.started_at,
            submitted_at=now,
            evaluated_at=now,
        )
        self._practice.update_attempt(evaluated)
        return self._describe_attempts([evaluated])[0]

    def list_attempts(self, *, limit: int, offset: int) -> AttemptPage:
        """One page of the learner's attempts, newest first.

        An installation where setup has not run has no learner and therefore no
        attempts, which is an empty page rather than a failure.

        Raises:
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        learner = resolve_local_learner(self._learners)
        if learner is None:
            return AttemptPage(attempts=(), total=0)
        records = self._practice.list_attempts(learner_id=learner.id, limit=limit, offset=offset)
        return AttemptPage(
            attempts=self._describe_attempts(records),
            total=self._practice.count_attempts(learner_id=learner.id),
        )

    def read_attempt(self, attempt_id: uuid.UUID) -> AttemptDetail:
        """One of the learner's attempts, with what became of each question.

        An attempt still in progress reads back **without** its expected answers
        and explanations, so opening a result before submitting reveals nothing.

        Raises:
            AttemptNotFoundError: No such attempt, or it is not the learner's.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        return self._describe_attempts([self._require_own_attempt(attempt_id)])[0]

    # --- Internals ----------------------------------------------------------

    def _require_learner(self) -> LearnerRecord:
        """The local learner, or a refusal naming what is missing."""
        learner = resolve_local_learner(self._learners)
        if learner is None:
            raise LearnerNotSetUpError(
                "No learner is stored, so no checkpoint quiz can be assembled."
            )
        return learner

    def _require_own_quiz(self, quiz_id: uuid.UUID) -> QuizRecord:
        """One of the learner's quizzes, or a refusal.

        A quiz belonging to somebody else is reported as missing rather than as
        forbidden, the rule every learner-owned read follows.
        """
        learner = resolve_local_learner(self._learners)
        record = None if learner is None else self._practice.find_quiz(quiz_id)
        if record is None or learner is None or record.learner_id != learner.id:
            raise QuizNotFoundError(f"No checkpoint quiz is stored with identifier {quiz_id}.")
        return record

    def _require_own_attempt(self, attempt_id: uuid.UUID) -> AttemptRecord:
        """One of the learner's attempts, or a refusal."""
        learner = resolve_local_learner(self._learners)
        record = None if learner is None else self._practice.find_attempt(attempt_id)
        if record is None or learner is None or record.learner_id != learner.id:
            raise AttemptNotFoundError(f"No quiz attempt is stored with identifier {attempt_id}.")
        return record

    def _validated_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[PracticeTopic, ...]:
        """The topics a quiz request names, checked against what is stored."""
        if not topic_ids:
            raise MissingQuizTopicError(
                "A checkpoint quiz covers at least one topic. Choose the topics to practise."
            )
        if len(topic_ids) > MAX_QUIZ_TOPICS:
            raise TooManyQuizTopicsError(
                f"A quiz may cover at most {MAX_QUIZ_TOPICS} topics in one request; "
                f"{len(topic_ids)} were given."
            )
        if len(set(topic_ids)) != len(topic_ids):
            raise DuplicateQuizTopicError("A topic is named more than once. Name each one once.")
        stored = {topic.id: topic for topic in self._practice.list_topics(topic_ids)}
        missing = [topic_id for topic_id in topic_ids if topic_id not in stored]
        if missing:
            raise UnknownTopicError(f"No topic is stored with identifier {missing[0]}.")
        return _in_curriculum_order([stored[topic_id] for topic_id in topic_ids])

    def _quiz_topics(
        self, quiz_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, tuple[PracticeTopic, ...]]:
        """The topics each quiz covers, named, in one query for the page."""
        links = self._practice.list_quiz_topics(quiz_ids)
        wanted = {topic_id for ids in links.values() for topic_id in ids}
        topics = {topic.id: topic for topic in self._practice.list_topics(sorted(wanted))}
        return {
            quiz_id: _in_curriculum_order(
                [topics[topic_id] for topic_id in ids if topic_id in topics]
            )
            for quiz_id, ids in links.items()
        }

    def _describe_attempts(self, records: Sequence[AttemptRecord]) -> tuple[AttemptDetail, ...]:
        """Attach each attempt's quiz, topics, and per-question outcomes."""
        quiz_ids = sorted({record.checkpoint_quiz_id for record in records})
        quizzes = {quiz.id: quiz for quiz in self._practice.list_quizzes(quiz_ids)}
        topics = self._quiz_topics(quiz_ids)
        answers = self._practice.list_attempt_answers([record.id for record in records])
        questions = {quiz_id: self._practice.list_quiz_questions(quiz_id) for quiz_id in quiz_ids}

        return tuple(
            AttemptDetail(
                id=record.id,
                learner_id=record.learner_id,
                checkpoint_quiz_id=record.checkpoint_quiz_id,
                quiz_title=(
                    quizzes[record.checkpoint_quiz_id].title
                    if record.checkpoint_quiz_id in quizzes
                    else ""
                ),
                status=record.status,
                started_at=record.started_at,
                submitted_at=record.submitted_at,
                evaluated_at=record.evaluated_at,
                topics=topics.get(record.checkpoint_quiz_id, ()),
                outcomes=_outcomes(
                    questions.get(record.checkpoint_quiz_id, ()),
                    answers.get(record.id, ()),
                    marked=record.status == EVALUATED,
                ),
            )
            for record in records
        )


def _outcomes(
    questions: Sequence[QuestionRecord],
    answers: Sequence[AttemptAnswerRecord],
    *,
    marked: bool,
) -> tuple[AttemptOutcome, ...]:
    """What became of each question, in the order the quiz asks them.

    `marked` decides whether the expected answer and the explanation are
    included. An attempt still in progress carries neither, so reading a result
    early reveals nothing — the same rule QZ-002 applies to the quiz itself.
    """
    by_question = {answer.question_id: answer for answer in answers}
    return tuple(
        AttemptOutcome(
            position=position,
            question_id=question.id,
            prompt=question.prompt,
            options=question.options,
            chosen_option_key=(
                by_question[question.id].chosen_option_key if question.id in by_question else None
            ),
            expected_option_key=question.expected_option_key if marked else None,
            explanation=question.explanation if marked else None,
            is_correct=(
                by_question[question.id].is_correct if question.id in by_question else None
            ),
        )
        for position, question in enumerate(questions, start=1)
    )


def _asked(questions: Sequence[QuestionRecord]) -> tuple[QuizQuestionView, ...]:
    """The questions a quiz asks, learner-safe and in the quiz's own order."""
    return tuple(
        QuizQuestionView(
            position=position,
            question_id=question.id,
            prompt=question.prompt,
            options=question.options,
        )
        for position, question in enumerate(questions, start=1)
    )


def _validated_answers(
    answers: Sequence[AnswerSubmission], questions: Sequence[QuestionRecord]
) -> tuple[SubmittedAnswer, ...]:
    """The answers a submission carries, checked against the quiz's questions.

    A question the submission omits is not an error: it is unanswered, and
    `mark_attempt` records it as such. What is refused is an answer naming a
    question this quiz does not ask, the same question answered twice, or an
    option the question does not offer — each of which means the client has a bug
    that silence would hide.
    """
    asked = {question.id: question for question in questions}
    seen: set[uuid.UUID] = set()
    submitted: list[SubmittedAnswer] = []
    for answer in answers:
        question = asked.get(answer.question_id)
        if question is None:
            raise UnknownQuestionError(
                f"This quiz does not ask a question with identifier {answer.question_id}."
            )
        if answer.question_id in seen:
            raise DuplicateAnswerError(
                "A question is answered more than once. Send one answer per question."
            )
        if answer.option_key not in {option.key for option in question.options}:
            raise UnknownOptionError(
                f"'{answer.option_key}' is not an option this question offers."
            )
        seen.add(answer.question_id)
        submitted.append(
            SubmittedAnswer(question_id=answer.question_id, chosen_option_key=answer.option_key)
        )
    return tuple(submitted)


def _in_curriculum_order(topics: Sequence[PracticeTopic]) -> tuple[PracticeTopic, ...]:
    """Topics ordered by subject and then by name.

    A stable, readable order rather than a meaningful one: nothing here ranks a
    topic against another, and a quiz's coverage is a list, not a sequence of
    priorities.
    """
    return tuple(sorted(topics, key=lambda topic: (topic.subject_name, topic.name)))


def _title_for(topics: Sequence[PracticeTopic]) -> str:
    """What a quiz is called: the topics it covers, in words.

    Composed by LearnFlow rather than asked of the learner, because the title is
    a description of the quiz's coverage rather than a name they chose. It states
    no figure — "three topics" would be a count of the plan, not of the learner,
    but naming them reads better and needs no rule about which counts are
    permitted.
    """
    names = [topic.name for topic in topics]
    if len(names) == 1:
        return f"Practice: {names[0]}"
    return f"Practice: {', '.join(names[:-1])} and {names[-1]}"
