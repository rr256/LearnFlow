"""SQLAlchemy implementation of the study-plan repository port.

Serves PLN-001, PLN-002, and PLN-003. It maps rows to the application's plain
records and back, and reads the curriculum rows a plan item describes.

It decides nothing. Which topics belong in a plan, what order they go in, which
day each lands on, and what replaces what are all settled above this layer
(docs/architecture/dependency-rules.md).

The session's transaction is owned by the caller. Nothing here commits.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.application.dto.study_plan import ACTIVE, StudyPlanFilters
from app.application.ports.curriculum_seed_repository import SubjectRecord, TopicRecord
from app.application.ports.study_plan_repository import PlanItemRecord, StudyPlanRecord
from app.infrastructure.persistence.curriculum import Subject, Topic
from app.infrastructure.persistence.learner_planning import PlanItem, StudyPlan


class SqlAlchemyStudyPlanRepository:
    """Reads and writes study plans and their items through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one unit of work."""
        self._session = session

    def count_study_plans(self, *, learner_id: uuid.UUID, filters: StudyPlanFilters) -> int:
        """How many of this learner's plans match, ignoring any page window."""
        total = self._session.scalar(
            select(func.count()).select_from(StudyPlan).where(*_filters(learner_id, filters))
        )
        return total or 0

    def list_study_plans(
        self, *, learner_id: uuid.UUID, filters: StudyPlanFilters, limit: int, offset: int
    ) -> tuple[StudyPlanRecord, ...]:
        """One page of the learner's plans, newest first.

        `id` breaks a tie on `created_at`, so a page boundary cannot repeat or
        skip a plan -- which matters here more than elsewhere, because one
        generation writes a roadmap and its week in the same transaction and they
        share a timestamp.
        """
        models = self._session.scalars(
            select(StudyPlan)
            .where(*_filters(learner_id, filters))
            .order_by(StudyPlan.created_at.desc(), StudyPlan.id)
            .limit(limit)
            .offset(offset)
        )
        return tuple(_plan_record(model) for model in models)

    def find_study_plan(self, study_plan_id: uuid.UUID) -> StudyPlanRecord | None:
        """The plan with this identifier, or None."""
        model = self._session.get(StudyPlan, study_plan_id)
        return None if model is None else _plan_record(model)

    def list_active_study_plans(self, study_goal_id: uuid.UUID) -> tuple[StudyPlanRecord, ...]:
        """Every `active` plan belonging to this goal."""
        models = self._session.scalars(
            select(StudyPlan).where(
                StudyPlan.study_goal_id == study_goal_id, StudyPlan.status == ACTIVE
            )
        )
        return tuple(_plan_record(model) for model in models)

    def add_study_plan(self, record: StudyPlanRecord) -> None:
        """Store a new study plan."""
        self._session.add(
            StudyPlan(
                id=record.id,
                learner_id=record.learner_id,
                study_goal_id=record.study_goal_id,
                plan_type=record.plan_type,
                period_start=record.period_start,
                period_end=record.period_end,
                status=record.status,
                generation_reason=record.generation_reason,
            )
        )

    def update_study_plan(self, record: StudyPlanRecord) -> None:
        """Overwrite the stored plan identified by ``record.id``."""
        model = self._session.get(StudyPlan, record.id)
        if model is None:
            raise LookupError(f"Study plan {record.id} is not stored.")
        model.plan_type = record.plan_type
        model.period_start = record.period_start
        model.period_end = record.period_end
        model.status = record.status
        model.generation_reason = record.generation_reason

    def count_plan_items(self, study_plan_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        """How many items each plan named holds, keyed by plan identifier."""
        if not study_plan_ids:
            return {}
        rows = self._session.execute(
            select(PlanItem.study_plan_id, func.count())
            .where(PlanItem.study_plan_id.in_(study_plan_ids))
            .group_by(PlanItem.study_plan_id)
        ).all()
        return {study_plan_id: count for study_plan_id, count in rows}

    def list_plan_items(self, study_plan_id: uuid.UUID) -> tuple[PlanItemRecord, ...]:
        """Every item of one plan."""
        models = self._session.scalars(
            select(PlanItem).where(PlanItem.study_plan_id == study_plan_id)
        )
        return tuple(_item_record(model) for model in models)

    def add_plan_item(self, record: PlanItemRecord) -> None:
        """Store a new plan item."""
        self._session.add(
            PlanItem(
                id=record.id,
                study_plan_id=record.study_plan_id,
                topic_id=record.topic_id,
                action_type=record.action_type,
                scheduled_for=record.scheduled_for,
                estimated_minutes=record.estimated_minutes,
                priority=record.priority,
                status=record.status,
                recommendation_reason=record.recommendation_reason,
            )
        )

    def list_subjects(self, curriculum_version_id: uuid.UUID) -> tuple[SubjectRecord, ...]:
        """Every subject of this version."""
        models = self._session.scalars(
            select(Subject).where(Subject.curriculum_version_id == curriculum_version_id)
        )
        return tuple(
            SubjectRecord(
                id=model.id,
                curriculum_version_id=model.curriculum_version_id,
                code=model.code,
                name=model.name,
                description=model.description,
                position=model.position,
            )
            for model in models
        )

    def list_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[TopicRecord, ...]:
        """The topics named, in no particular order."""
        if not topic_ids:
            return ()
        models = self._session.scalars(select(Topic).where(Topic.id.in_(topic_ids)))
        return tuple(
            TopicRecord(
                id=model.id,
                subject_id=model.subject_id,
                parent_topic_id=model.parent_topic_id,
                code=model.code,
                name=model.name,
                description=model.description,
                position=model.position,
                is_trackable=model.is_trackable,
            )
            for model in models
        )


def _filters(learner_id: uuid.UUID, filters: StudyPlanFilters) -> list[ColumnElement[bool]]:
    """The WHERE clauses selecting one learner's plans, narrowed as asked.

    Shared by the count and the page deliberately, for the reason the topic
    progress repository records: a `total` computed under a different predicate
    from the rows it counts is worse than no `total` at all.
    """
    clauses: list[ColumnElement[bool]] = [StudyPlan.learner_id == learner_id]
    if filters.study_goal_id is not None:
        clauses.append(StudyPlan.study_goal_id == filters.study_goal_id)
    if filters.plan_type is not None:
        clauses.append(StudyPlan.plan_type == filters.plan_type)
    if filters.status is not None:
        clauses.append(StudyPlan.status == filters.status)
    return clauses


def _plan_record(model: StudyPlan) -> StudyPlanRecord:
    return StudyPlanRecord(
        id=model.id,
        learner_id=model.learner_id,
        study_goal_id=model.study_goal_id,
        plan_type=model.plan_type,
        period_start=model.period_start,
        period_end=model.period_end,
        status=model.status,
        generation_reason=model.generation_reason,
    )


def _item_record(model: PlanItem) -> PlanItemRecord:
    return PlanItemRecord(
        id=model.id,
        study_plan_id=model.study_plan_id,
        topic_id=model.topic_id,
        action_type=model.action_type,
        scheduled_for=model.scheduled_for,
        estimated_minutes=model.estimated_minutes,
        priority=model.priority,
        status=model.status,
        recommendation_reason=model.recommendation_reason,
    )
