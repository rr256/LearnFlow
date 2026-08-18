"""The checkpoint-marking domain rules.

Pure functions over plain values, so every case here is exhaustive rather than
representative: the whole point of keeping option keying, quiz ordering, and
answer marking out of the use case is that they can be tested this way.

Two properties are asserted repeatedly because the product depends on them:
marking is **deterministic**, and an **unanswered question is not a wrong one**.
"""

import uuid
from datetime import UTC, datetime

import pytest

from app.domain.checkpoint_marking import (
    MAX_OPTIONS,
    MIN_OPTIONS,
    OPTION_KEYS,
    AskableQuestion,
    SubmittedAnswer,
    arrange_questions,
    assign_option_keys,
    mark_answer,
    mark_attempt,
)

WRITTEN_AT = datetime(2026, 8, 18, 9, 0, tzinfo=UTC)


def question(*, written_at: datetime = WRITTEN_AT, expected: str = "a") -> AskableQuestion:
    return AskableQuestion(id=uuid.uuid4(), written_at=written_at, expected_option_key=expected)


# -- keying options -----------------------------------------------------------


def test_options_are_keyed_by_position():
    options = assign_option_keys(["8", "10", "16", "1024"])

    assert [option.key for option in options] == ["a", "b", "c", "d"]
    assert [option.text for option in options] == ["8", "10", "16", "1024"]


def test_keying_the_same_options_twice_gives_the_same_keys():
    """Determinism: a stored expected answer cannot come to name a moved position."""
    assert assign_option_keys(["p", "q", "r"]) == assign_option_keys(["p", "q", "r"])


@pytest.mark.parametrize("count", [MIN_OPTIONS, 3, 4, 5, MAX_OPTIONS])
def test_every_permitted_option_count_is_keyed(count):
    options = assign_option_keys([f"option {index}" for index in range(count)])

    assert [option.key for option in options] == list(OPTION_KEYS[:count])


@pytest.mark.parametrize("count", [0, 1, MAX_OPTIONS + 1])
def test_an_impossible_option_count_is_refused(count):
    """One option is not a choice, and more than six outruns the keys."""
    with pytest.raises(ValueError, match="options"):
        assign_option_keys([f"option {index}" for index in range(count)])


# -- arranging a quiz ---------------------------------------------------------


def test_a_quiz_asks_questions_in_the_order_they_were_written():
    first = question(written_at=datetime(2026, 8, 1, tzinfo=UTC))
    second = question(written_at=datetime(2026, 8, 2, tzinfo=UTC))
    third = question(written_at=datetime(2026, 8, 3, tzinfo=UTC))

    assert arrange_questions([third, first, second]) == (first.id, second.id, third.id)


def test_two_questions_written_in_the_same_instant_are_ordered_by_identifier():
    """A tie is broken deterministically rather than left to the database."""
    one = question()
    other = question()

    arranged = arrange_questions([one, other])

    assert arranged == tuple(sorted((one.id, other.id)))


def test_arranging_the_same_questions_twice_gives_the_same_order():
    written = [question(written_at=datetime(2026, 8, day, tzinfo=UTC)) for day in (3, 1, 2)]

    assert arrange_questions(written) == arrange_questions(reversed(written))


def test_arranging_nothing_gives_nothing():
    assert arrange_questions([]) == ()


# -- marking one answer -------------------------------------------------------


def test_the_expected_option_is_correct():
    assert mark_answer(expected_option_key="c", chosen_option_key="c") is True


def test_another_option_is_not_correct():
    assert mark_answer(expected_option_key="c", chosen_option_key="a") is False


def test_an_unanswered_question_is_neither():
    """The distinction `quiz_attempt_answers.is_correct` is nullable to record."""
    assert mark_answer(expected_option_key="c", chosen_option_key=None) is None


def test_marking_is_case_sensitive_and_exact():
    """Keys are assigned by LearnFlow, so nothing here forgives a near miss."""
    assert mark_answer(expected_option_key="a", chosen_option_key="A") is False


# -- marking an attempt -------------------------------------------------------


def test_every_question_of_the_quiz_appears_in_the_result():
    asked = [question(expected="a"), question(expected="b"), question(expected="c")]

    marked = mark_attempt(asked, [SubmittedAnswer(asked[0].id, "a")])

    assert [outcome.question_id for outcome in marked] == [item.id for item in asked]


def test_outcomes_keep_the_order_the_quiz_asks():
    asked = [question(), question(), question()]

    marked = mark_attempt(asked, [SubmittedAnswer(asked[2].id, "a")])

    assert [outcome.question_id for outcome in marked] == [item.id for item in asked]


def test_an_omitted_question_is_unanswered_rather_than_wrong():
    asked = [question(expected="a"), question(expected="b")]

    marked = mark_attempt(asked, [SubmittedAnswer(asked[0].id, "a")])

    assert marked[0].is_correct is True
    assert marked[1].is_correct is None
    assert marked[1].was_answered is False


def test_an_answer_naming_a_question_the_quiz_does_not_ask_is_ignored():
    """Refusing one is the use case's job; it needs to name the identifier."""
    asked = [question(expected="a")]

    marked = mark_attempt(asked, [SubmittedAnswer(uuid.uuid4(), "b")])

    assert len(marked) == 1
    assert marked[0].is_correct is None


def test_marking_the_same_attempt_twice_gives_the_same_outcomes():
    asked = [question(expected="a"), question(expected="b")]
    answers = [SubmittedAnswer(asked[0].id, "b"), SubmittedAnswer(asked[1].id, "b")]

    assert mark_attempt(asked, answers) == mark_attempt(asked, answers)


def test_an_attempt_with_no_answers_marks_every_question_unanswered():
    asked = [question(), question()]

    marked = mark_attempt(asked, [])

    assert [outcome.is_correct for outcome in marked] == [None, None]


def test_an_outcome_carries_the_expected_key_so_a_result_can_explain_itself():
    asked = [question(expected="d")]

    marked = mark_attempt(asked, [SubmittedAnswer(asked[0].id, "a")])

    assert marked[0].expected_option_key == "d"
    assert marked[0].chosen_option_key == "a"


def test_nothing_marked_carries_a_score():
    """The result is per-question outcomes and nothing more (ADR-033)."""
    marked = mark_attempt([question(expected="a")], [SubmittedAnswer(uuid.uuid4(), "a")])

    fields = set(vars(type(marked[0]))["__slots__"])
    assert not fields & {"score", "marks", "awarded_marks", "total", "percent"}
