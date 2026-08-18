"""The deterministic rules that decide what a checkpoint quiz asks, and how one answer is marked.

Three rules live here, and all are pure functions over plain values: how a
question's options are keyed, which order a quiz asks its questions in, and
whether one submitted answer matches the expected one. They are domain rules for
the reason the rules in `study_planning` and `revision_scheduling` are -- they
are the part a learner would recognise as *the marking*, and everything around
them is reading records and writing them back.

Being pure is the point.
[FR-009](../../../docs/requirements/functional.md#fr-009-topic-checkpoint-practice)
requires that objective answers can be scored automatically, and
docs/ai/learnflow-agents.md requires the product to stay deterministic and usable
with no AI provider reachable. **No AI marks anything here.** A function whose
output depends only on its arguments can be tested exhaustively and explained to
a learner who disagrees with it; one that asks a model cannot.

**Nothing here counts, totals, ranks, or scores.** A marked attempt is a sequence
of per-question outcomes and nothing more: there is no total, no mark, no
percentage, and no comparison between two attempts or two learners. That is the
rule docs/domain/terminology.md states -- a number that rates the learner is
forbidden by name -- read for an assessment, and it is why this module returns
`MarkedAnswer` values rather than a score. See ADR-033.

**An unanswered question is not a wrong one.** `mark_answer` returns `None` for a
question the learner left alone, which is the distinction
`quiz_attempt_answers.is_correct` is nullable to record. Treating silence as an
error would state something about the learner that they did not.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

MIN_OPTIONS = 2
"""The fewest options a multiple-choice question may offer.

One option is not a choice, and a question offering it would mark every learner
correct. This is a property of the question form rather than a rule about study.
"""

MAX_OPTIONS = 6
"""The most options a multiple-choice question may offer.

A bound rather than a judgement: it keeps one question's `options` payload small
and its keys inside `OPTION_KEYS` below. It sits above the four a GATE
multiple-choice question conventionally offers.
"""

OPTION_KEYS: tuple[str, ...] = ("a", "b", "c", "d", "e", "f")
"""The keys options are given, in order, up to `MAX_OPTIONS`.

Assigned by position rather than accepted from a caller, so two questions cannot
key the same position differently and a stored answer always names an option the
question actually offers. Lowercase Latin letters are what a printed paper uses,
which is what a learner transcribing their own practice will expect.
"""


@dataclass(frozen=True, slots=True)
class AnswerOption:
    """One option a multiple-choice question offers.

    `key` is assigned by position; `text` is the learner's own wording.
    """

    key: str
    text: str


@dataclass(frozen=True, slots=True)
class AskableQuestion:
    """One question a quiz may ask, with what is needed to order and mark it.

    `written_at` and `id` are what `arrange_questions` orders by. Neither is a
    judgement about the question: there is deliberately no difficulty, no
    weighting, and no quality signal, because ordering by one would rank two
    questions against each other, which nothing in LearnFlow does.
    """

    id: uuid.UUID
    written_at: datetime
    expected_option_key: str


@dataclass(frozen=True, slots=True)
class SubmittedAnswer:
    """One answer a learner submitted, before it is marked."""

    question_id: uuid.UUID
    chosen_option_key: str | None


@dataclass(frozen=True, slots=True)
class MarkedAnswer:
    """What became of one question in one attempt.

    Deliberately carries no marks and no score. `is_correct` is `True`, `False`,
    or `None` for a question the learner left unanswered -- three outcomes, none
    of them a number.
    """

    question_id: uuid.UUID
    chosen_option_key: str | None
    expected_option_key: str
    is_correct: bool | None

    @property
    def was_answered(self) -> bool:
        """Whether the learner chose an option for this question."""
        return self.chosen_option_key is not None


def assign_option_keys(texts: Sequence[str]) -> tuple[AnswerOption, ...]:
    """Key each option text by its position: the first is `a`, the second `b`.

    Deterministic and total over `MIN_OPTIONS`..`MAX_OPTIONS`, so the same list
    of options always produces the same keys and a stored `expected_answer`
    cannot come to name a position that has moved.

    Args:
        texts: The option wordings, in the order the learner gave them.

    Returns:
        One `AnswerOption` per text, keyed by position.

    Raises:
        ValueError: Fewer than `MIN_OPTIONS` or more than `MAX_OPTIONS` texts.
    """
    if not MIN_OPTIONS <= len(texts) <= MAX_OPTIONS:
        raise ValueError(
            f"A multiple-choice question offers between {MIN_OPTIONS} and "
            f"{MAX_OPTIONS} options; {len(texts)} were given."
        )
    return tuple(
        AnswerOption(key=OPTION_KEYS[index], text=text) for index, text in enumerate(texts)
    )


def arrange_questions(questions: Iterable[AskableQuestion]) -> tuple[uuid.UUID, ...]:
    """The order a quiz asks its questions in: the order they were written.

    The whole rule, and it is stated to the learner in those words. Ordering by
    when a question was written is explainable without reference to anything
    about the learner, cannot be read as a ranking, and is stable -- asking for
    the same quiz twice arranges it identically, which is what makes a
    regenerated quiz comparable to the one before it.

    `id` breaks a tie, so two questions written in the same transaction still
    arrange deterministically rather than by whatever order the database
    returned them in.

    Args:
        questions: The questions linked to the topics the learner chose.

    Returns:
        Their identifiers, in the order the quiz asks them.
    """
    return tuple(
        question.id
        for question in sorted(questions, key=lambda question: (question.written_at, question.id))
    )


def mark_answer(*, expected_option_key: str, chosen_option_key: str | None) -> bool | None:
    """Whether one submitted answer matches the expected one.

    Args:
        expected_option_key: The key the question's author marked correct.
        chosen_option_key: The key the learner chose, or None if they chose none.

    Returns:
        True or False for an answered question, and **None for an unanswered
        one** -- silence is not an error, and the nullable
        `quiz_attempt_answers.is_correct` exists to keep the two apart.
    """
    if chosen_option_key is None:
        return None
    return chosen_option_key == expected_option_key


def mark_attempt(
    questions: Sequence[AskableQuestion], answers: Iterable[SubmittedAnswer]
) -> tuple[MarkedAnswer, ...]:
    """Mark every question of an attempt, in the order the quiz asks them.

    **Every question of the quiz appears in the result**, whether or not the
    learner answered it, so a result never quietly omits what was skipped. An
    answer naming a question the quiz does not ask is ignored here; refusing one
    is the use case's job, because it needs to say which identifier was wrong.

    Args:
        questions: The quiz's questions, as `arrange_questions` ordered them.
        answers: What the learner submitted, in any order.

    Returns:
        One `MarkedAnswer` per question, in the quiz's own order. **No total, no
        score, and no count** -- see the module docstring.
    """
    chosen = {answer.question_id: answer.chosen_option_key for answer in answers}
    return tuple(
        MarkedAnswer(
            question_id=question.id,
            chosen_option_key=chosen.get(question.id),
            expected_option_key=question.expected_option_key,
            is_correct=mark_answer(
                expected_option_key=question.expected_option_key,
                chosen_option_key=chosen.get(question.id),
            ),
        )
        for question in questions
    )
