"""The checkpoint-quiz use case (QZ-001, QZ-002, QZ-003, QZ-005, QZ-006, QZ-007).

Run against fakes, so what is asserted is the rule rather than the query. The
database counterpart is tests/integration/test_checkpoint_practice_api.py.

Four product rules are asserted repeatedly because the feature rests on them: a
quiz asks **every** ready question for the chosen topics and selects none, a quiz
being taken **never carries its answers**, an **unanswered question is not a wrong
one**, and a result **carries no score**.
"""

import uuid

import pytest

from app.application.dto.checkpoint_practice import (
    AnswerSubmission,
    NewQuiz,
    QuestionChanges,
)
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_checkpoint_quizzes import (
    AttemptAlreadyMarkedError,
    AttemptNotFoundError,
    DuplicateAnswerError,
    DuplicateQuizTopicError,
    LearnerNotSetUpError,
    MissingQuizTopicError,
    NoQuestionsForTopicsError,
    QuizNotFoundError,
    TooManyQuizTopicsError,
    UnknownOptionError,
    UnknownQuestionError,
    UnknownTopicError,
)
from tests.unit.fake_learner_repository import FakeLearnerRepository, learner
from tests.unit.practice_fixtures import Practising, a_question


@pytest.fixture
def practising() -> Practising:
    return Practising()


def write(practising: Practising, **fields: object):
    """Write one question against the trackable topic by default."""
    fields.setdefault("topic_ids", (practising.topic.id,))
    return practising.author().write(a_question(**fields))


def assembled(practising: Practising, *topics):
    """Assemble a quiz over the topics given, or the trackable one."""
    chosen = topics or (practising.topic,)
    return practising.quizzes().assemble(NewQuiz(topic_ids=tuple(topic.id for topic in chosen)))


# -- assembling ---------------------------------------------------------------


def test_a_quiz_asks_every_ready_question_for_the_chosen_topics(practising):
    """LearnFlow selects none and leaves none out: choosing a few would be a ranking."""
    write(practising, prompt="First")
    write(practising, prompt="Second")
    write(practising, prompt="Third")

    quiz = assembled(practising)

    assert [question.prompt for question in quiz.questions] == ["First", "Second", "Third"]


def test_a_quiz_asks_them_in_the_order_they_were_written(practising):
    write(practising, prompt="Older")
    write(practising, prompt="Newer")

    quiz = assembled(practising)

    assert [question.prompt for question in quiz.questions] == ["Older", "Newer"]
    assert [question.position for question in quiz.questions] == [1, 2]


def test_assembling_the_same_quiz_twice_asks_the_same_questions_in_the_same_order(practising):
    """Deterministic, with no AI provider: the same inputs give the same quiz."""
    write(practising, prompt="First")
    write(practising, prompt="Second")

    first = assembled(practising)
    again = assembled(practising)

    assert [question.prompt for question in first.questions] == [
        question.prompt for question in again.questions
    ]


def test_a_retired_question_is_not_asked(practising):
    kept = write(practising, prompt="Kept")
    set_aside = write(practising, prompt="Set aside")
    practising.author().update(set_aside.id, QuestionChanges(status="retired"))

    quiz = assembled(practising)

    assert [question.question_id for question in quiz.questions] == [kept.id]


def test_a_question_covering_two_chosen_topics_is_asked_once(practising):
    write(practising, topic_ids=(practising.topic.id, practising.other_topic.id))

    quiz = assembled(practising, practising.topic, practising.other_topic)

    assert len(quiz.questions) == 1


def test_a_quiz_names_the_topics_it_covers(practising):
    write(practising)

    quiz = assembled(practising)

    assert [topic.name for topic in quiz.topics] == ["CPU scheduling"]


def test_a_quiz_is_titled_from_the_topics_it_covers(practising):
    write(practising, topic_ids=(practising.topic.id, practising.other_topic.id))

    quiz = assembled(practising, practising.topic, practising.other_topic)

    assert quiz.title == "Practice: CPU scheduling and Page replacement"


def test_a_quiz_covering_no_topic_is_refused(practising):
    """ADR-008's rule, which no database constraint can express."""
    with pytest.raises(MissingQuizTopicError):
        practising.quizzes().assemble(NewQuiz(topic_ids=()))


def test_a_topic_that_is_not_stored_is_refused(practising):
    with pytest.raises(UnknownTopicError):
        practising.quizzes().assemble(NewQuiz(topic_ids=(uuid.uuid4(),)))


def test_the_same_topic_named_twice_is_refused(practising):
    with pytest.raises(DuplicateQuizTopicError):
        practising.quizzes().assemble(NewQuiz(topic_ids=(practising.topic.id, practising.topic.id)))


def test_more_topics_than_one_request_may_cover_is_refused(practising):
    with pytest.raises(TooManyQuizTopicsError):
        practising.quizzes().assemble(NewQuiz(topic_ids=tuple(uuid.uuid4() for _ in range(101))))


def test_a_quiz_for_topics_with_no_questions_is_refused_rather_than_stored(practising):
    """A quiz that asks nothing cannot be attempted."""
    with pytest.raises(NoQuestionsForTopicsError):
        assembled(practising)

    assert practising.practice.quizzes == []


def test_assembling_without_a_learner_is_refused(practising):
    practising.learners = FakeLearnerRepository(())

    with pytest.raises(LearnerNotSetUpError):
        assembled(practising)


def test_assembling_with_more_than_one_learner_stored_is_refused(practising):
    write(practising)
    practising.learners = FakeLearnerRepository((learner(), learner()))

    with pytest.raises(AmbiguousLocalLearnerError):
        assembled(practising)


# -- reading a quiz -----------------------------------------------------------


def test_a_quiz_being_taken_carries_no_expected_answer(practising):
    """QZ-002's whole point: the answer is not sent before the learner answers."""
    write(practising)
    quiz = assembled(practising)

    read = practising.quizzes().read_quiz(quiz.id)

    assert not any(hasattr(question, "expected_option_key") for question in read.questions)
    assert not any(hasattr(question, "explanation") for question in read.questions)


def test_a_quiz_being_taken_still_carries_its_options(practising):
    write(practising)
    quiz = assembled(practising)

    read = practising.quizzes().read_quiz(quiz.id)

    assert [option.key for option in read.questions[0].options] == ["a", "b", "c", "d"]


def test_a_quiz_that_is_not_stored_is_reported_as_missing(practising):
    with pytest.raises(QuizNotFoundError):
        practising.quizzes().read_quiz(uuid.uuid4())


def test_another_learners_quiz_is_reported_as_missing(practising):
    write(practising)
    quiz = assembled(practising)
    practising.learners = FakeLearnerRepository((learner(),))

    with pytest.raises(QuizNotFoundError):
        practising.quizzes().read_quiz(quiz.id)


# -- starting an attempt ------------------------------------------------------


def test_starting_an_attempt_records_when_it_began(practising):
    write(practising)
    quiz = assembled(practising)

    attempt, created = practising.quizzes().start_attempt(quiz.id)

    assert created is True
    assert attempt.status == "in_progress"
    assert attempt.started_at is not None


def test_asking_twice_returns_the_attempt_already_open(practising):
    """The position REV-004 takes: asking twice creates nothing the second time."""
    write(practising)
    quiz = assembled(practising)
    first, _ = practising.quizzes().start_attempt(quiz.id)

    again, created = practising.quizzes().start_attempt(quiz.id)

    assert created is False
    assert again.id == first.id
    assert len(practising.practice.attempts) == 1


def test_an_attempt_in_progress_reveals_no_answers(practising):
    write(practising)
    quiz = assembled(practising)

    attempt, _ = practising.quizzes().start_attempt(quiz.id)

    assert [outcome.expected_option_key for outcome in attempt.outcomes] == [None]
    assert [outcome.explanation for outcome in attempt.outcomes] == [None]


def test_starting_an_attempt_at_a_quiz_that_is_not_stored_is_refused(practising):
    with pytest.raises(QuizNotFoundError):
        practising.quizzes().start_attempt(uuid.uuid4())


# -- submitting ---------------------------------------------------------------


def started(practising: Practising, *prompts: str):
    """Write the questions named, assemble a quiz, and begin an attempt."""
    for prompt in prompts:
        write(practising, prompt=prompt)
    quiz = assembled(practising)
    attempt, _ = practising.quizzes().start_attempt(quiz.id)
    return quiz, attempt


def test_the_expected_option_is_marked_correct(practising):
    quiz, attempt = started(practising, "First")

    marked = practising.quizzes().submit(
        attempt.id, [AnswerSubmission(quiz.questions[0].question_id, "b")]
    )

    assert marked.outcomes[0].is_correct is True


def test_another_option_is_marked_not_correct(practising):
    quiz, attempt = started(practising, "First")

    marked = practising.quizzes().submit(
        attempt.id, [AnswerSubmission(quiz.questions[0].question_id, "a")]
    )

    assert marked.outcomes[0].is_correct is False
    assert marked.outcomes[0].chosen_option_key == "a"


def test_an_omitted_question_reads_as_unanswered_rather_than_wrong(practising):
    quiz, attempt = started(practising, "First", "Second")

    marked = practising.quizzes().submit(
        attempt.id, [AnswerSubmission(quiz.questions[0].question_id, "b")]
    )

    assert marked.outcomes[1].is_correct is None
    assert marked.outcomes[1].chosen_option_key is None


def test_submitting_nothing_marks_every_question_unanswered(practising):
    _, attempt = started(practising, "First", "Second")

    marked = practising.quizzes().submit(attempt.id, [])

    assert [outcome.is_correct for outcome in marked.outcomes] == [None, None]
    assert marked.status == "evaluated"


def test_a_marked_result_shows_the_expected_answer_and_the_explanation(practising):
    quiz, attempt = started(practising, "First")

    marked = practising.quizzes().submit(
        attempt.id, [AnswerSubmission(quiz.questions[0].question_id, "a")]
    )

    assert marked.outcomes[0].expected_option_key == "b"
    assert marked.outcomes[0].explanation == "1 KiB is 2^10 bytes, so ten bits address it."


def test_a_marked_result_carries_no_score(practising):
    """The whole rule ADR-033 fixes: outcomes, never a total."""
    quiz, attempt = started(practising, "First", "Second")

    marked = practising.quizzes().submit(
        attempt.id, [AnswerSubmission(quiz.questions[0].question_id, "b")]
    )

    fields = set(vars(type(marked))["__slots__"])
    assert not fields & {"score", "max_score", "correct_count", "percent", "marks"}


def test_submitting_records_when_it_was_marked(practising):
    _, attempt = started(practising, "First")

    marked = practising.quizzes().submit(attempt.id, [])

    assert marked.submitted_at is not None
    assert marked.evaluated_at is not None


def test_submitting_twice_is_refused(practising):
    """A record of what happened is not edited after the fact."""
    _, attempt = started(practising, "First")
    practising.quizzes().submit(attempt.id, [])

    with pytest.raises(AttemptAlreadyMarkedError):
        practising.quizzes().submit(attempt.id, [])


def test_an_answer_naming_a_question_the_quiz_does_not_ask_is_refused(practising):
    _, attempt = started(practising, "First")

    with pytest.raises(UnknownQuestionError):
        practising.quizzes().submit(attempt.id, [AnswerSubmission(uuid.uuid4(), "a")])


def test_the_same_question_answered_twice_is_refused(practising):
    quiz, attempt = started(practising, "First")
    question_id = quiz.questions[0].question_id

    with pytest.raises(DuplicateAnswerError):
        practising.quizzes().submit(
            attempt.id,
            [AnswerSubmission(question_id, "a"), AnswerSubmission(question_id, "b")],
        )


def test_an_option_the_question_does_not_offer_is_refused(practising):
    quiz, attempt = started(practising, "First")

    with pytest.raises(UnknownOptionError):
        practising.quizzes().submit(
            attempt.id, [AnswerSubmission(quiz.questions[0].question_id, "z")]
        )


def test_submitting_moves_nothing_else(practising):
    """No learning stage, no plan, no plan item, and no revision."""
    quiz, attempt = started(practising, "First")

    practising.quizzes().submit(attempt.id, [AnswerSubmission(quiz.questions[0].question_id, "b")])

    assert len(practising.practice.quizzes) == 1
    assert len(practising.practice.attempts) == 1


def test_submitting_an_attempt_that_is_not_stored_is_refused(practising):
    with pytest.raises(AttemptNotFoundError):
        practising.quizzes().submit(uuid.uuid4(), [])


# -- reading attempts ---------------------------------------------------------


def test_attempts_are_listed_newest_first(practising):
    write(practising, prompt="First")
    first_quiz = assembled(practising)
    practising.quizzes().start_attempt(first_quiz.id)
    write(practising, prompt="Second", topic_ids=(practising.other_topic.id,))
    second_quiz = practising.quizzes().assemble(NewQuiz(topic_ids=(practising.other_topic.id,)))
    practising.quizzes().start_attempt(second_quiz.id)

    page = practising.quizzes().list_attempts(limit=25, offset=0)

    assert [attempt.checkpoint_quiz_id for attempt in page.attempts] == [
        second_quiz.id,
        first_quiz.id,
    ]
    assert page.total == 2


def test_an_installation_with_no_learner_lists_no_attempts(practising):
    practising.learners = FakeLearnerRepository(())

    page = practising.quizzes().list_attempts(limit=25, offset=0)

    assert page.attempts == ()
    assert page.total == 0


def test_a_read_attempt_names_the_quiz_it_belongs_to(practising):
    quiz, attempt = started(practising, "First")

    read = practising.quizzes().read_attempt(attempt.id)

    assert read.quiz_title == quiz.title


def test_an_attempt_that_is_not_stored_is_reported_as_missing(practising):
    with pytest.raises(AttemptNotFoundError):
        practising.quizzes().read_attempt(uuid.uuid4())


def test_another_learners_attempt_is_reported_as_missing(practising):
    _, attempt = started(practising, "First")
    practising.learners = FakeLearnerRepository((learner(),))

    with pytest.raises(AttemptNotFoundError):
        practising.quizzes().read_attempt(attempt.id)
