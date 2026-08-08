"""An in-memory stand-in for the study-plan repository port.

Plans and items are held in insertion order and returned in it, so a use case
relying on the store to sort fails here rather than passing by accident against a
database that happened to return rows conveniently. The one exception is the
plan page, whose order the port owns because a page cannot be sorted after it has
been sliced — and there the fake reverses insertion order, matching the
`created_at desc` the SQLAlchemy adapter applies.

The controlled values are asserted on write, mirroring the database `CHECK`s: a
fake accepting a plan type or an item length PostgreSQL would refuse would let a
use case test pass on a shape the real database cannot store.
"""

import uuid
from collections.abc import Sequence

from app.application.dto.study_plan import (
    ACTIVE,
    COMPLETED,
    PLAN_ITEM_ACTIONS,
    PLAN_ITEM_STATUSES,
    PLAN_STATUSES,
    PLAN_TYPES,
    StudyPlanFilters,
)
from app.application.ports.curriculum_seed_repository import SubjectRecord, TopicRecord
from app.application.ports.study_plan_repository import PlanItemRecord, StudyPlanRecord


class FakeStudyPlanRepository:
    """Stores plans and items in lists, over fixed curriculum reference data."""

    def __init__(
        self,
        *,
        subjects: Sequence[SubjectRecord] = (),
        topics: Sequence[TopicRecord] = (),
        plans: Sequence[StudyPlanRecord] = (),
        items: Sequence[PlanItemRecord] = (),
    ) -> None:
        self.subjects = list(subjects)
        self.topics = list(topics)
        self.plans: list[StudyPlanRecord] = list(plans)
        self.items: list[PlanItemRecord] = list(items)
        # Plans the store has actually been told about. A plan added but not
        # flushed is pending, and an item referencing it would be refused by
        # `fk_plan_items_study_plan_id_study_plans`.
        self._flushed: set[uuid.UUID] = {record.id for record in self.plans}

    def count_study_plans(self, *, learner_id: uuid.UUID, filters: StudyPlanFilters) -> int:
        return len(self._matching(learner_id, filters))

    def list_study_plans(
        self, *, learner_id: uuid.UUID, filters: StudyPlanFilters, limit: int, offset: int
    ) -> tuple[StudyPlanRecord, ...]:
        matching = list(reversed(self._matching(learner_id, filters)))
        return tuple(matching[offset : offset + limit])

    def find_study_plan(self, study_plan_id: uuid.UUID) -> StudyPlanRecord | None:
        return next((record for record in self.plans if record.id == study_plan_id), None)

    def list_active_study_plans(self, study_goal_id: uuid.UUID) -> tuple[StudyPlanRecord, ...]:
        return tuple(
            record
            for record in self.plans
            if record.study_goal_id == study_goal_id and record.status == ACTIVE
        )

    def add_study_plan(self, record: StudyPlanRecord) -> None:
        assert record.plan_type in PLAN_TYPES, f"{record.plan_type!r} is not a plan type"
        assert record.status in PLAN_STATUSES, f"{record.status!r} is not a plan status"
        self.plans.append(record)

    def update_study_plan(self, record: StudyPlanRecord) -> None:
        assert record.status in PLAN_STATUSES, f"{record.status!r} is not a plan status"
        for index, stored in enumerate(self.plans):
            if stored.id == record.id:
                self.plans[index] = record
                return
        raise AssertionError(f"study plan {record.id} is not stored")

    def count_plan_items(self, study_plan_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        counts: dict[uuid.UUID, int] = {}
        for item in self.items:
            if item.study_plan_id in study_plan_ids:
                counts[item.study_plan_id] = counts.get(item.study_plan_id, 0) + 1
        return counts

    def list_plan_items(self, study_plan_id: uuid.UUID) -> tuple[PlanItemRecord, ...]:
        return tuple(item for item in self.items if item.study_plan_id == study_plan_id)

    def find_plan_item(self, plan_item_id: uuid.UUID) -> PlanItemRecord | None:
        return next((item for item in self.items if item.id == plan_item_id), None)

    def add_plan_item(self, record: PlanItemRecord) -> None:
        assert record.action_type in PLAN_ITEM_ACTIONS, f"{record.action_type!r} is not an action"
        assert record.status in PLAN_ITEM_STATUSES, f"{record.status!r} is not an item status"
        assert record.estimated_minutes is None or record.estimated_minutes > 0, (
            "an item cannot be estimated at zero minutes or fewer"
        )
        # Mirrors `fk_plan_items_study_plan_id_study_plans`. Without this the
        # fake accepted an item whose plan had not reached the store, which is
        # how a foreign-key violation reached CI having passed every unit test.
        assert record.study_plan_id in self._flushed, (
            f"plan {record.study_plan_id} has not been flushed, so the database "
            "would refuse this item"
        )
        self.items.append(record)

    def update_plan_item(self, record: PlanItemRecord) -> None:
        assert record.status in PLAN_ITEM_STATUSES, f"{record.status!r} is not an item status"
        # The database has no such constraint — `status` and `completed_at` are
        # separate columns — so this guards the application rule instead: a
        # timestamp on an item that is not completed would be a completion
        # nothing can read back, and a completed item without one could not say
        # when.
        assert (record.completed_at is not None) == (record.status == COMPLETED), (
            f"{record.status!r} and completed_at={record.completed_at!r} disagree"
        )
        for index, stored in enumerate(self.items):
            if stored.id == record.id:
                self.items[index] = record
                return
        raise AssertionError(f"plan item {record.id} is not stored")

    def flush(self) -> None:
        """Make every plan added so far visible to the items that reference it."""
        self._flushed.update(record.id for record in self.plans)

    def list_subjects(self, curriculum_version_id: uuid.UUID) -> tuple[SubjectRecord, ...]:
        return tuple(
            record
            for record in self.subjects
            if record.curriculum_version_id == curriculum_version_id
        )

    def list_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[TopicRecord, ...]:
        return tuple(record for record in self.topics if record.id in set(topic_ids))

    def _matching(self, learner_id: uuid.UUID, filters: StudyPlanFilters) -> list[StudyPlanRecord]:
        return [
            record
            for record in self.plans
            if record.learner_id == learner_id
            and (filters.study_goal_id is None or record.study_goal_id == filters.study_goal_id)
            and (filters.plan_type is None or record.plan_type == filters.plan_type)
            and (filters.status is None or record.status == filters.status)
        ]
