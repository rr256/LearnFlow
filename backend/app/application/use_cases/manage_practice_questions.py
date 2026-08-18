"""Recording the practice questions a learner writes, finding them, and setting one aside.

Serves QZ-008 to QZ-010, which hold the question bank the checkpoint quizzes in
`manage_checkpoint_quizzes` are assembled from. Together they begin
[FR-009](../../../docs/requirements/functional.md#fr-009-topic-checkpoint-practice).

**The learner writes every question.** Nothing is generated, retrieved, scraped,
or shipped: no AI provider is reached, no previous-year paper is bundled, and no
external source is consulted. `source_type` is always `curated`, and the two
other values the column accepts wait on capabilities that do not exist — which is
the position ADR-032 took when it shipped no curated resources either. This keeps
the repository free of third-party question content and its licensing.

**A question is never edited.** QZ-010 changes its status and nothing else. A
prompt, its options, its expected answer, and its topics are fixed once written,
because `quiz_attempt_answers` references a question by identifier: rewriting a
prompt would silently rewrite the history of every attempt already marked against
it. A learner corrects a question by retiring it and writing another, which keeps
both readable — the position ADR-022 takes for a superseded plan.

**Nothing is deleted.** `retired` sets a question aside so no new quiz asks it,
and it is reversible.

**Nothing is recommended, ranked, scored, or counted.** No question is suggested,
graded for difficulty, promoted above another, or counted on any screen. There is
no `difficulty` column, deliberately.

**Nothing else moves.** Writing or retiring a question writes no learning stage,
no plan, no plan item, and no revision — writing practice says nothing about
whether a topic is understood.
"""

import uuid
from collections.abc import Sequence

from app.application.dto.checkpoint_practice import (
    CURATED,
    MARKABLE_QUESTION_TYPES,
    MAX_TOPIC_LINKS,
    QUESTION_STATUSES,
    READY,
    NewQuestion,
    PracticeTopic,
    QuestionChanges,
    QuestionDetail,
    QuestionFilters,
    QuestionPage,
    QuestionRecord,
)
from app.application.ports.checkpoint_practice_repository import CheckpointPracticeRepository
from app.application.ports.clock import Clock
from app.application.ports.learner_repository import LearnerRecord, LearnerRepository
from app.application.use_cases.local_learner import resolve_local_learner
from app.domain.checkpoint_marking import (
    MAX_OPTIONS,
    MIN_OPTIONS,
    AnswerOption,
    assign_option_keys,
)


class PracticeQuestionError(Exception):
    """Base class for the refusals this use case makes."""


class LearnerNotSetUpError(PracticeQuestionError):
    """No learner is stored, so no question can be written."""


class QuestionNotFoundError(PracticeQuestionError):
    """No such question is stored, or another learner wrote it."""


class MissingPromptError(PracticeQuestionError):
    """A question with no prompt, which nothing could answer."""


class UnusableOptionsError(PracticeQuestionError):
    """Too few options, too many, or one with no wording."""


class UnknownExpectedAnswerError(PracticeQuestionError):
    """The expected answer names no option the question offers."""


class DuplicateOptionError(PracticeQuestionError):
    """The same option wording offered more than once.

    Refused rather than collapsed: two identical options make a question
    unanswerable, because a learner choosing the other one would be marked wrong
    for the same answer.
    """


class UnknownQuestionStatusError(PracticeQuestionError):
    """A status a learner may not ask for."""


class EmptyQuestionUpdateError(PracticeQuestionError):
    """An update naming no field to change."""


class MissingTopicLinkError(PracticeQuestionError):
    """A question linked to no topic, which no quiz could ever ask."""


class UnknownTopicError(PracticeQuestionError):
    """A topic identifier naming nothing stored."""


class DuplicateTopicLinkError(PracticeQuestionError):
    """The same topic named more than once in one request."""


class TooManyTopicLinksError(PracticeQuestionError):
    """More topics named than one request may link."""


class ManagePracticeQuestions:
    """Writes, reads, and retires the practice questions a learner has authored."""

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

    def write(self, new_question: NewQuestion) -> QuestionDetail:
        """Record one practice question the learner has written.

        The caller owns the transaction: this writes through the repository but
        never commits.

        Option keys are assigned by position by the domain rule, never accepted
        from the caller, so a stored expected answer always names an option the
        question offers.

        A question may cover **any** stored topic, including one that only groups
        subtopics — the position ADR-032 takes for a resource, and deliberately
        unlike PRG-004, which refuses a *stage* on a grouping topic.

        Raises:
            LearnerNotSetUpError: No learner exists to own the question.
            AmbiguousLocalLearnerError: More than one learner is stored.
            MissingPromptError: The prompt is empty.
            UnusableOptionsError: Too few or too many options, or a blank one.
            DuplicateOptionError: The same option wording appears twice.
            UnknownExpectedAnswerError: The expected answer names no option.
            MissingTopicLinkError: No topic was named.
            UnknownTopicError: A topic identifier names nothing stored.
            DuplicateTopicLinkError: A topic was named more than once.
            TooManyTopicLinksError: More topics than one request may link.
        """
        learner = self._require_learner()

        prompt = _require_prompt(new_question.prompt)
        options = _validated_options(new_question.option_texts)
        expected_key = _expected_key(options, new_question.correct_option_index)
        topic_ids = self._validated_topics(new_question.topic_ids)

        record = QuestionRecord(
            id=uuid.uuid4(),
            author_learner_id=learner.id,
            # The one form this build can mark. See MARKABLE_QUESTION_TYPES.
            question_type=MARKABLE_QUESTION_TYPES[0],
            # The learner wrote it, so it is curated material. Nothing here is
            # generated, and nothing is a verified previous-year question.
            source_type=CURATED,
            prompt=prompt,
            options=options,
            expected_option_key=expected_key,
            explanation=_blank_to_none(new_question.explanation),
            # Every question is written ready. Retiring is a later statement the
            # learner makes, never a state anything starts in.
            status=READY,
            # Read from the server's clock rather than accepted from a caller,
            # the rule ADR-021 fixed for `plan_items.completed_at`. A quiz is
            # ordered by this, so a caller able to set it could reorder a quiz.
            written_at=self._clock.now(),
        )
        self._practice.add_question(record)
        self._practice.replace_question_topic_links(question_id=record.id, topic_ids=topic_ids)
        return self._describe([record])[0]

    def list_questions(self, *, filters: QuestionFilters, limit: int, offset: int) -> QuestionPage:
        """One page of the learner's practice questions, newest first.

        An installation where setup has not run has no learner and therefore no
        questions, which is an empty page rather than a failure. A `topic_id`
        matching nothing is an empty page too, while an unknown *status* is
        refused — a caller asking for one has misread the contract, and an empty
        page would let it keep doing so.

        Raises:
            UnknownQuestionStatusError: The status filter names an unknown state.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        if filters.status is not None:
            _require_known_status(filters.status)

        learner = resolve_local_learner(self._learners)
        if learner is None:
            return QuestionPage(questions=(), total=0)

        records = self._practice.list_questions(
            learner_id=learner.id, filters=filters, limit=limit, offset=offset
        )
        return QuestionPage(
            questions=self._describe(records),
            total=self._practice.count_questions(learner_id=learner.id, filters=filters),
        )

    def update(self, question_id: uuid.UUID, changes: QuestionChanges) -> QuestionDetail:
        """Set a question aside, or bring it back.

        The caller owns the transaction.

        **Status is the only thing that may change**; see `QuestionChanges`.
        Retiring is reversible and destroys nothing: a retired question stays
        readable and stays in every quiz already assembled from it, because those
        quizzes have attempts marked against them.

        Raises:
            QuestionNotFoundError: No such question, or another learner wrote it.
            EmptyQuestionUpdateError: The update names no field to change.
            UnknownQuestionStatusError: A status a learner may not ask for.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        if changes.is_empty:
            raise EmptyQuestionUpdateError(
                "The request names no field to change. Send a status: "
                f"{', '.join(QUESTION_STATUSES)}."
            )
        status = changes.status
        if status is None:  # pragma: no cover - `is_empty` above already refused this
            raise EmptyQuestionUpdateError("The request names no field to change.")
        _require_known_status(status)

        record = self._require_own_question(question_id)
        changed = QuestionRecord(
            id=record.id,
            author_learner_id=record.author_learner_id,
            question_type=record.question_type,
            source_type=record.source_type,
            prompt=record.prompt,
            options=record.options,
            expected_option_key=record.expected_option_key,
            explanation=record.explanation,
            status=status,
            written_at=record.written_at,
        )
        self._practice.update_question(changed)
        return self._describe([changed])[0]

    def _require_learner(self) -> LearnerRecord:
        """The local learner, or a refusal naming what is missing."""
        learner = resolve_local_learner(self._learners)
        if learner is None:
            raise LearnerNotSetUpError(
                "No learner is stored, so no practice question can be written."
            )
        return learner

    def _require_own_question(self, question_id: uuid.UUID) -> QuestionRecord:
        """One of the learner's questions, or a refusal.

        A question written by somebody else is reported as missing rather than as
        forbidden, the rule every learner-owned read follows.
        """
        learner = resolve_local_learner(self._learners)
        record = None if learner is None else self._practice.find_question(question_id)
        if record is None or learner is None or record.author_learner_id != learner.id:
            raise QuestionNotFoundError(
                f"No practice question is stored with identifier {question_id}."
            )
        return record

    def _validated_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[uuid.UUID, ...]:
        """The topics a request names, checked against what is stored.

        **At least one is required**, unlike a resource: a question linked to no
        topic could never be asked, because a quiz is assembled by topic. A
        duplicate is refused rather than collapsed, which is GOAL-005's rule for
        a day named twice.
        """
        if not topic_ids:
            raise MissingTopicLinkError(
                "A practice question must cover at least one topic, so a quiz can find it."
            )
        if len(topic_ids) > MAX_TOPIC_LINKS:
            raise TooManyTopicLinksError(
                f"A question may name at most {MAX_TOPIC_LINKS} topics in one request; "
                f"{len(topic_ids)} were given."
            )
        if len(set(topic_ids)) != len(topic_ids):
            raise DuplicateTopicLinkError("A topic is named more than once. Name each one once.")
        stored = {topic.id for topic in self._practice.list_topics(topic_ids)}
        missing = [topic_id for topic_id in topic_ids if topic_id not in stored]
        if missing:
            raise UnknownTopicError(f"No topic is stored with identifier {missing[0]}.")
        return tuple(topic_ids)

    def _describe(self, records: Sequence[QuestionRecord]) -> tuple[QuestionDetail, ...]:
        """Attach the topics each question covers, in one query for the page."""
        links = self._practice.list_question_topic_links([record.id for record in records])
        wanted = {topic_id for ids in links.values() for topic_id in ids}
        topics = {topic.id: topic for topic in self._practice.list_topics(sorted(wanted))}
        return tuple(
            QuestionDetail(
                id=record.id,
                author_learner_id=record.author_learner_id,
                question_type=record.question_type,
                source_type=record.source_type,
                prompt=record.prompt,
                options=record.options,
                expected_option_key=record.expected_option_key,
                explanation=record.explanation,
                status=record.status,
                written_at=record.written_at,
                topics=_named(links.get(record.id, ()), topics),
            )
            for record in records
        )


def _named(
    topic_ids: Sequence[uuid.UUID], topics: dict[uuid.UUID, PracticeTopic]
) -> tuple[PracticeTopic, ...]:
    """The stored topics among those named, in curriculum order.

    A link whose topic has since gone is left out rather than reported as a
    broken reference: the curriculum is reference data and is not casually
    deleted, so this is a safety net rather than an expected state.
    """
    named = [topics[topic_id] for topic_id in topic_ids if topic_id in topics]
    return tuple(sorted(named, key=lambda topic: (topic.subject_name, topic.name)))


def _require_prompt(prompt: str) -> str:
    """The prompt, trimmed, or a refusal."""
    trimmed = prompt.strip()
    if not trimmed:
        raise MissingPromptError("A practice question needs a prompt.")
    return trimmed


def _validated_options(texts: Sequence[str]) -> tuple[AnswerOption, ...]:
    """The options a request offers, keyed by position, or a refusal."""
    trimmed = tuple(text.strip() for text in texts)
    if any(not text for text in trimmed):
        raise UnusableOptionsError("Every option needs some wording.")
    if len(set(trimmed)) != len(trimmed):
        raise DuplicateOptionError(
            "Two options say the same thing, so the question cannot be answered. "
            "Make each option distinct."
        )
    try:
        return assign_option_keys(trimmed)
    except ValueError as error:
        raise UnusableOptionsError(
            f"A question offers between {MIN_OPTIONS} and {MAX_OPTIONS} options; "
            f"{len(trimmed)} were given."
        ) from error


def _expected_key(options: Sequence[AnswerOption], correct_option_index: int) -> str:
    """The key of the option marked correct, or a refusal."""
    if not 0 <= correct_option_index < len(options):
        raise UnknownExpectedAnswerError(
            f"The expected answer names option {correct_option_index + 1}, "
            f"but the question offers {len(options)}."
        )
    return options[correct_option_index].key


def _require_known_status(status: str) -> None:
    """Refuse a status this build does not accept."""
    if status not in QUESTION_STATUSES:
        raise UnknownQuestionStatusError(
            f"'{status}' is not a status a practice question may be set to. "
            f"Use one of: {', '.join(QUESTION_STATUSES)}."
        )


def _blank_to_none(value: str | None) -> str | None:
    """Trim, and treat an empty string as absent.

    A form posts an untouched field as an empty string; storing that would make
    "left blank" and "cleared" different values that read identically.
    """
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None
