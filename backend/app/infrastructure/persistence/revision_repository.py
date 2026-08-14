"""SQLAlchemy implementation of the revision repository port.

Serves REV-001 to REV-004. It maps rows to the application's plain records and
back, reads the curriculum rows a revision describes, and answers the one
question scheduling asks of the planning tables: which topics has this learner
completed planned work on, and when.

It decides nothing. What makes a revision due, how long a topic waits, which
statuses a learner may ask for, and whether a topic already has one waiting are
all settled by the use case and the domain rules
(docs/architecture/dependency-rules.md).

The session's transaction is owned by the caller. Nothing here commits.
"""

import uuid
from collections.abc import Mapping, Sequence
from datetime import date

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session

from app.application.dto.revision import (
    COMPLETED,
    SETTLED_REVISION_STATUSES,
    RevisionFilters,
    RevisionRecord,
    RevisionTopic,
)
from app.infrastructure.persistence.curriculum import Subject, Topic
from app.infrastructure.persistence.learner_planning import PlanItem, StudyPlan
from app.infrastructure.persistence.progress import LearnerTopicProgress
from app.infrastructure.persistence.progress import RevisionRecord as RevisionRow


class SqlAlchemyRevisionRepository:
    """Reads and writes a learner's revisions through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one unit of work."""
        self._session = session

    def count_revisions(self, *, learner_id: uuid.UUID, filters: RevisionFilters) -> int:
        """How many of this learner's revisions match, ignoring any page window."""
        total = self._session.scalar(
            select(func.count()).select_from(RevisionRow).where(*_filters(learner_id, filters))
        )
        return int(total or 0)

    def list_revisions(
        self,
        *,
        learner_id: uuid.UUID,
        filters: RevisionFilters,
        limit: int,
        offset: int,
    ) -> tuple[RevisionRecord, ...]:
        """One page of the learner's revisions, earliest due date first."""
        rows = self._session.scalars(
            _ordered(select(RevisionRow).where(*_filters(learner_id, filters)))
            .limit(limit)
            .offset(offset)
        ).all()
        return tuple(_record(row) for row in rows)

    def list_all_revisions(self, learner_id: uuid.UUID) -> tuple[RevisionRecord, ...]:
        """Every revision this learner has, earliest due date first."""
        rows = self._session.scalars(
            _ordered(select(RevisionRow).where(RevisionRow.learner_id == learner_id))
        ).all()
        return tuple(_record(row) for row in rows)

    def find_revision(self, revision_id: uuid.UUID) -> RevisionRecord | None:
        """The revision with this identifier, or None."""
        row = self._session.get(RevisionRow, revision_id)
        return None if row is None else _record(row)

    def add_revision(self, record: RevisionRecord) -> None:
        """Store a new revision."""
        self._session.add(
            RevisionRow(
                id=record.id,
                learner_id=record.learner_id,
                topic_id=record.topic_id,
                plan_item_id=record.plan_item_id,
                due_on=record.due_on,
                scheduled_for=record.scheduled_for,
                status=record.status,
                trigger_type=record.trigger_type,
                recommendation_reason=record.recommendation_reason,
                completed_at=record.completed_at,
            )
        )

    def update_revision(self, record: RevisionRecord) -> None:
        """Store a changed revision.

        Raises:
            LookupError: The revision is not stored. The use case has already
                established that it is, so reaching this means the row vanished
                between the read and the write.
        """
        row = self._session.get(RevisionRow, record.id)
        if row is None:
            raise LookupError(f"No revision is stored with identifier {record.id}.")
        row.due_on = record.due_on
        row.scheduled_for = record.scheduled_for
        row.status = record.status
        row.completed_at = record.completed_at

    def list_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[RevisionTopic, ...]:
        """The topics named, in no particular order."""
        if not topic_ids:
            return ()
        rows = self._session.execute(
            select(Topic.id, Topic.code, Topic.name, Subject.id, Subject.name)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(Topic.id.in_(topic_ids))
        ).all()
        return tuple(
            RevisionTopic(
                id=row[0], code=row[1], name=row[2], subject_id=row[3], subject_name=row[4]
            )
            for row in rows
        )

    def list_recorded_stages(
        self, *, learner_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, str]:
        """The learning stage recorded for each topic named, where one exists."""
        if not topic_ids:
            return {}
        rows = self._session.execute(
            select(LearnerTopicProgress.topic_id, LearnerTopicProgress.learning_stage).where(
                LearnerTopicProgress.learner_id == learner_id,
                LearnerTopicProgress.topic_id.in_(topic_ids),
            )
        ).all()
        return {topic_id: stage for topic_id, stage in rows}

    def list_completed_topic_work(
        self, learner_id: uuid.UUID
    ) -> tuple[tuple[uuid.UUID, uuid.UUID, date], ...]:
        """Each topic this learner completed planned work on, earliest completion.

        Every plan of the learner's is read, superseded ones included: superseding
        a plan does not un-complete the work done under it.

        Grouped in SQL rather than in Python so a learner with many superseded
        plans does not pull every completed item across the boundary to discard
        most of them. `min(completed_at)` picks the earliest completion, and the
        plan item reported is the one that carries it.
        """
        earliest = (
            select(
                PlanItem.topic_id.label("topic_id"),
                func.min(PlanItem.completed_at).label("completed_at"),
            )
            .join(StudyPlan, StudyPlan.id == PlanItem.study_plan_id)
            .where(
                StudyPlan.learner_id == learner_id,
                PlanItem.status == COMPLETED,
                PlanItem.topic_id.is_not(None),
                PlanItem.completed_at.is_not(None),
            )
            .group_by(PlanItem.topic_id)
            .subquery()
        )
        rows = self._session.execute(
            select(PlanItem.topic_id, PlanItem.id, PlanItem.completed_at)
            .join(StudyPlan, StudyPlan.id == PlanItem.study_plan_id)
            .join(
                earliest,
                (PlanItem.topic_id == earliest.c.topic_id)
                & (PlanItem.completed_at == earliest.c.completed_at),
            )
            .where(StudyPlan.learner_id == learner_id, PlanItem.status == COMPLETED)
            .order_by(PlanItem.topic_id, PlanItem.id)
        ).all()

        # A topic completed twice at the same instant would appear twice; the
        # first by plan item identifier wins, so the result is deterministic.
        seen: dict[uuid.UUID, tuple[uuid.UUID, uuid.UUID, date]] = {}
        for topic_id, plan_item_id, completed_at in rows:
            if topic_id not in seen:
                seen[topic_id] = (topic_id, plan_item_id, completed_at.date())
        return tuple(seen.values())


def _filters(learner_id: uuid.UUID, filters: RevisionFilters) -> tuple[ColumnElement[bool], ...]:
    """The conditions a listed revision must meet.

    `due_only` is expressed here as "unsettled", not as a date comparison: what
    counts as due needs today, which is the use case's to supply through the
    clock port, and a repository that read one would put a rule below the layer
    that owns it.
    """
    conditions: list[ColumnElement[bool]] = [RevisionRow.learner_id == learner_id]
    if filters.status is not None:
        conditions.append(RevisionRow.status == filters.status)
    if filters.due_only:
        conditions.append(RevisionRow.status.not_in(tuple(SETTLED_REVISION_STATUSES)))
    return tuple(conditions)


def _ordered(statement: Select[tuple[RevisionRow]]) -> Select[tuple[RevisionRow]]:
    """Earliest due date first, then by identifier.

    The identifier breaks a tie two revisions falling due on one day would
    otherwise leave to the database, which would let one page repeat or omit a
    record.
    """
    return statement.order_by(RevisionRow.due_on, RevisionRow.id)


def _record(row: RevisionRow) -> RevisionRecord:
    """Map a stored row onto the application's plain record."""
    return RevisionRecord(
        id=row.id,
        learner_id=row.learner_id,
        topic_id=row.topic_id,
        plan_item_id=row.plan_item_id,
        due_on=row.due_on,
        scheduled_for=row.scheduled_for,
        status=row.status,
        trigger_type=row.trigger_type,
        recommendation_reason=row.recommendation_reason,
        completed_at=row.completed_at,
    )
