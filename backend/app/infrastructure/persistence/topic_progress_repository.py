"""SQLAlchemy implementation of the topic-progress repository port.

Serves PRG-002 and PRG-004. It maps rows to the application's plain records and
back, and reads the curriculum rows a record describes.

It decides nothing. Which stages are valid, whether a grouping topic may hold
one, and what an absent record means are all settled by the use case
(docs/architecture/dependency-rules.md).

The session's transaction is owned by the caller. Nothing here commits.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session

from app.application.dto.topic_progress import TopicProgressRecord, TopicProgressTopic
from app.infrastructure.persistence.curriculum import Subject, Topic
from app.infrastructure.persistence.progress import LearnerTopicProgress


class SqlAlchemyTopicProgressRepository:
    """Reads and writes learner topic progress through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one unit of work."""
        self._session = session

    def find_topic(self, topic_id: uuid.UUID) -> TopicProgressTopic | None:
        """The topic with this identifier, or None."""
        row = self._session.execute(_topic_query().where(Topic.id == topic_id)).first()
        return None if row is None else _topic(row)

    def list_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[TopicProgressTopic, ...]:
        """The topics named, in no particular order."""
        if not topic_ids:
            return ()
        rows = self._session.execute(_topic_query().where(Topic.id.in_(topic_ids))).all()
        return tuple(_topic(row) for row in rows)

    def count_topic_progress(
        self, *, learner_id: uuid.UUID, curriculum_version_id: uuid.UUID | None
    ) -> int:
        """How many of this learner's records match, ignoring any page window."""
        total = self._session.scalar(
            select(func.count())
            .select_from(LearnerTopicProgress)
            .where(*_filters(learner_id, curriculum_version_id))
        )
        return total or 0

    def list_topic_progress(
        self,
        *,
        learner_id: uuid.UUID,
        curriculum_version_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[TopicProgressRecord, ...]:
        """One page of the learner's records, newest first.

        `id` breaks a tie on `created_at`, so a page boundary cannot repeat or
        skip a record when two are written in the same transaction.
        """
        models = self._session.scalars(
            select(LearnerTopicProgress)
            .where(*_filters(learner_id, curriculum_version_id))
            .order_by(LearnerTopicProgress.created_at.desc(), LearnerTopicProgress.id)
            .limit(limit)
            .offset(offset)
        )
        return tuple(_progress_record(model) for model in models)

    def find_topic_progress(
        self, *, learner_id: uuid.UUID, topic_id: uuid.UUID
    ) -> TopicProgressRecord | None:
        """This learner's record for this topic, or None."""
        model = self._session.scalar(
            select(LearnerTopicProgress).where(
                LearnerTopicProgress.learner_id == learner_id,
                LearnerTopicProgress.topic_id == topic_id,
            )
        )
        return None if model is None else _progress_record(model)

    def add_topic_progress(self, record: TopicProgressRecord) -> None:
        """Store a new progress record."""
        self._session.add(
            LearnerTopicProgress(
                id=record.id,
                learner_id=record.learner_id,
                topic_id=record.topic_id,
                learning_stage=record.learning_stage,
                stage_source=record.stage_source,
            )
        )

    def update_topic_progress(self, record: TopicProgressRecord) -> None:
        """Overwrite the stored record identified by ``record.id``."""
        model = self._session.get(LearnerTopicProgress, record.id)
        if model is None:
            raise LookupError(f"Topic progress {record.id} is not stored.")
        model.learning_stage = record.learning_stage
        model.stage_source = record.stage_source


def _topic_query() -> Select[tuple[Topic, uuid.UUID]]:
    """Topics with the curriculum version they belong to, one join away.

    The version is not a column on `topics`; it is reached through the subject.
    Selecting it here means a caller placing a record in the hierarchy needs no
    second query.
    """
    return select(Topic, Subject.curriculum_version_id).join(
        Subject, Topic.subject_id == Subject.id
    )


def _filters(
    learner_id: uuid.UUID, curriculum_version_id: uuid.UUID | None
) -> list[ColumnElement[bool]]:
    """The WHERE clauses selecting one learner's records, optionally by version.

    The version filter reaches through two relations, because a curriculum
    version owns subjects and a subject owns topics. It is a subquery rather
    than a join so the count and the page share exactly one predicate; an
    unstored version identifier matches no subject and therefore no record,
    which is an empty result rather than an error.

    Shared by the count and the page deliberately. A `total` computed under a
    different predicate from the rows it counts is worse than no `total` at all.
    """
    clauses: list[ColumnElement[bool]] = [LearnerTopicProgress.learner_id == learner_id]
    if curriculum_version_id is not None:
        clauses.append(
            LearnerTopicProgress.topic_id.in_(
                select(Topic.id)
                .join(Subject, Topic.subject_id == Subject.id)
                .where(Subject.curriculum_version_id == curriculum_version_id)
            )
        )
    return clauses


def _topic(row: tuple[Topic, uuid.UUID]) -> TopicProgressTopic:
    model, curriculum_version_id = row
    return TopicProgressTopic(
        id=model.id,
        code=model.code,
        name=model.name,
        is_trackable=model.is_trackable,
        subject_id=model.subject_id,
        curriculum_version_id=curriculum_version_id,
    )


def _progress_record(model: LearnerTopicProgress) -> TopicProgressRecord:
    return TopicProgressRecord(
        id=model.id,
        learner_id=model.learner_id,
        topic_id=model.topic_id,
        learning_stage=model.learning_stage,
        stage_source=model.stage_source,
    )
