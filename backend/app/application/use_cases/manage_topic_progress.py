"""Read and record a learner's manual topic progress (PRG-002, PRG-004).

This is the first learner topic progress LearnFlow stores, and the rules it
holds are the ones FR-005 and ADR-017 fix.

It stores a *stage*, not *evidence*. docs/domain/terminology.md reserves
"evidence" for observed learning signals -- study activity, quiz outcomes,
external test results, mistakes -- and "stage" for the learner-visible
interpretation of them. Nothing here observes anything: the learner states the
interpretation directly, and `stage_source` records that they did.

**A stage is a supportive summary, not a score.** The five stages guide the next
action. Nothing here ranks them, compares them, or infers one from another; a
learner may move to any stage from any stage, including backwards, because
noticing that a topic needs more work is a legitimate thing to record.

**Absence is the neutral starting state.** A topic with no record has no stage,
which reads as *Not explored*. This use case never creates a record the learner
did not ask for, so listing progress before anything is recorded is an empty
page rather than 65 rows of nothing.

**A grouping topic cannot hold a stage.** `topics.is_trackable` says whether
progress can be recorded directly, and a topic that merely groups subtopics
cannot. Refusing it here names the offending field; nothing in the database
forbids it, because the rule is about what a topic *is* rather than about
referential integrity.

**Only the learner writes a stage today.** Every record is stored with
`stage_source` of `learner`. When quiz or external-test evidence begins
proposing one, that writer sets a different source and this one is unchanged --
which is the whole reason the column exists from the start.
"""

import uuid

from app.application.dto.topic_progress import (
    TopicProgressDetail,
    TopicProgressPage,
    TopicProgressRecord,
    TopicProgressTopic,
    TopicStageChange,
)
from app.application.ports.learner_repository import LearnerRepository
from app.application.ports.topic_progress_repository import TopicProgressRepository
from app.application.use_cases.local_learner import resolve_local_learner

LEARNING_STAGES: tuple[str, ...] = (
    "not_explored",
    "building_foundation",
    "developing_confidence",
    "practice_ready",
    "strong_understanding",
)
"""The stages `learner_topic_progress.learning_stage` accepts.

Mirrors the database `CHECK` and the display labels in
docs/domain/terminology.md. The order is the progression a learner moves along,
not a ranking: this module never compares two stages.
"""

LEARNER_STAGE_SOURCE = "learner"
"""What `stage_source` records for a stage the learner set themselves."""


class TopicProgressError(Exception):
    """A learner's topic progress could not be read or recorded as asked."""


class LearnerNotSetUpError(TopicProgressError):
    """No learner exists yet, so there is nobody to own a progress record."""


class TopicNotFoundError(TopicProgressError):
    """No topic with the requested identifier is stored."""


class TopicNotTrackableError(TopicProgressError):
    """The topic groups subtopics and cannot hold progress of its own."""


class UnknownLearningStageError(TopicProgressError):
    """The request names a stage the database would refuse."""


class TopicProgressIntegrityError(TopicProgressError):
    """A stored progress record points at a topic that is no longer stored.

    A foreign key makes this unreachable through the API. It is raised rather
    than papered over so a hand-edited database surfaces as a reported failure
    instead of a response with a nameless record in it.
    """


class ManageTopicProgress:
    """Serves the topic-progress endpoints through the ports below."""

    def __init__(
        self,
        *,
        learners: LearnerRepository,
        progress: TopicProgressRepository,
    ) -> None:
        """Wire the use case.

        Args:
            learners: Where the effective learner is resolved.
            progress: Where progress records are read and written, and where the
                topics they describe are read.
        """
        self._learners = learners
        self._progress = progress

    def list_topic_progress(
        self,
        *,
        curriculum_version_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> TopicProgressPage:
        """One page of the learner's recorded stages.

        A learner who has not been created yet has recorded nothing, which is an
        empty page rather than a failure: a client asking what it should show
        before setup has run is asking a reasonable question.

        Topics with no record are deliberately absent rather than reported as
        `not_explored`. This endpoint reports what the learner has recorded; the
        curriculum is where every topic is listed, and a client showing both
        joins them.

        Args:
            curriculum_version_id: Restrict to topics of this curriculum
                version. A version that is not stored matches nothing.
            limit: How many records to return. The caller validates the bound.
            offset: How many records to skip.

        Raises:
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        learner = resolve_local_learner(self._learners)
        if learner is None:
            return TopicProgressPage(records=(), total=0, limit=limit, offset=offset)

        records = self._progress.list_topic_progress(
            learner_id=learner.id,
            curriculum_version_id=curriculum_version_id,
            limit=limit,
            offset=offset,
        )
        topics = {
            topic.id: topic
            for topic in self._progress.list_topics([record.topic_id for record in records])
        }
        return TopicProgressPage(
            records=tuple(self._detail(record, topics.get(record.topic_id)) for record in records),
            total=self._progress.count_topic_progress(
                learner_id=learner.id, curriculum_version_id=curriculum_version_id
            ),
            limit=limit,
            offset=offset,
        )

    def record_stage(self, topic_id: uuid.UUID, change: TopicStageChange) -> TopicProgressDetail:
        """Record the learner's stage for one topic, creating the record if needed.

        The caller owns the transaction: this method writes through the
        repository but never commits.

        Recording the stage a topic already holds is accepted and writes
        nothing. A learner confirming what they already thought is not an error,
        and a repeated form submission must not fail on its second attempt.

        Raises:
            UnknownLearningStageError: The stage is not one of the five.
            TopicNotFoundError: No such topic is stored.
            TopicNotTrackableError: The topic only groups subtopics.
            LearnerNotSetUpError: No learner exists to own the record.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        if change.learning_stage not in LEARNING_STAGES:
            # The rejected value is deliberately not repeated back.
            # docs/api/conventions.md keeps it out of the error envelope, and
            # naming the five accepted stages is what a caller actually needs.
            raise UnknownLearningStageError(
                f"That is not a learning stage. Use one of: {', '.join(LEARNING_STAGES)}."
            )

        topic = self._progress.find_topic(topic_id)
        if topic is None:
            raise TopicNotFoundError(f"No topic is stored with identifier {topic_id}.")
        if not topic.is_trackable:
            raise TopicNotTrackableError(
                f"Topic {topic.name!r} groups subtopics and does not hold progress of its "
                "own. Record a stage against one of its subtopics instead."
            )

        learner = resolve_local_learner(self._learners)
        if learner is None:
            raise LearnerNotSetUpError(
                "No learner profile exists yet. Complete learner setup before recording progress."
            )

        existing = self._progress.find_topic_progress(learner_id=learner.id, topic_id=topic.id)
        if existing is None:
            record = TopicProgressRecord(
                id=uuid.uuid4(),
                learner_id=learner.id,
                topic_id=topic.id,
                learning_stage=change.learning_stage,
                stage_source=LEARNER_STAGE_SOURCE,
            )
            self._progress.add_topic_progress(record)
            return self._detail(record, topic)

        record = TopicProgressRecord(
            id=existing.id,
            learner_id=existing.learner_id,
            topic_id=existing.topic_id,
            learning_stage=change.learning_stage,
            # A learner editing a stage takes ownership of it, even where
            # evidence had proposed one. Nothing derives a stage yet, so today
            # this only ever rewrites `learner` with `learner`.
            stage_source=LEARNER_STAGE_SOURCE,
        )
        if record != existing:
            self._progress.update_topic_progress(record)
        return self._detail(record, topic)

    def _detail(
        self, record: TopicProgressRecord, topic: TopicProgressTopic | None
    ) -> TopicProgressDetail:
        if topic is None:
            raise TopicProgressIntegrityError(
                f"Topic progress {record.id} references topic {record.topic_id}, which is "
                "not stored."
            )
        return TopicProgressDetail(
            id=record.id,
            learner_id=record.learner_id,
            learning_stage=record.learning_stage,
            stage_source=record.stage_source,
            topic=topic,
        )
