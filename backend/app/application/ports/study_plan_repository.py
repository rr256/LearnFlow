"""The persistence port the study-plan endpoints work through.

It reads and writes the two learner-owned tables this feature adds — `study_plans`
and `plan_items` — and reads two kinds of row it does not own: the subjects and
topics a plan recommends work on. Those are curriculum reference data, read here
so that returning a plan stays one unit of work rather than one repository per
kind of row, which is the reason `TopicProgressRepository` reads topics too.

The port offers storage primitives only. Which topics belong in a plan, what
order they go in, and which day each lands on are rules, so the use case and the
domain decide them; infrastructure must not
(docs/architecture/dependency-rules.md).

Records are reused rather than redeclared where one already describes the row.
Ordering of a page is fixed here, for the reason `curriculum_repository` records:
a page cannot be ordered after it has been sliced. Items are the exception —
their order is `priority`, which the use case assigned, so it sorts them itself.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from app.application.dto.study_plan import StudyPlanFilters
from app.application.ports.curriculum_seed_repository import SubjectRecord, TopicRecord


@dataclass(frozen=True, slots=True)
class StudyPlanRecord:
    """A stored study plan.

    `learner_id` sits beside `study_goal_id` although the goal already names the
    learner. docs/database/schema.md carries both, and the required index leads on
    `learner_id`, so a learner's plans are reachable without joining through their
    goals.
    """

    id: uuid.UUID
    learner_id: uuid.UUID
    study_goal_id: uuid.UUID
    plan_type: str
    period_start: date | None
    period_end: date | None
    status: str
    generation_reason: str | None


@dataclass(frozen=True, slots=True)
class PlanItemRecord:
    """A stored plan item.

    `topic_id` is nullable because docs/database/schema.md allows an item that
    recommends work belonging to no single topic. Nothing writes one today: every
    item this planner produces names a topic.

    `completed_at` is null unless `status` is `completed`. The two are written
    together by PLN-004 and by nothing else — generation writes `planned` and no
    timestamp.
    """

    id: uuid.UUID
    study_plan_id: uuid.UUID
    topic_id: uuid.UUID | None
    action_type: str
    scheduled_for: date | None
    estimated_minutes: int | None
    priority: int
    status: str
    recommendation_reason: str | None
    completed_at: datetime | None = None


class StudyPlanRepository(Protocol):
    """Reads and writes the plans a learner has, and what is in them."""

    def count_study_plans(self, *, learner_id: uuid.UUID, filters: StudyPlanFilters) -> int:
        """How many of this learner's plans match, ignoring any page window."""
        ...

    def list_study_plans(
        self, *, learner_id: uuid.UUID, filters: StudyPlanFilters, limit: int, offset: int
    ) -> tuple[StudyPlanRecord, ...]:
        """One page of the learner's plans, newest first.

        A filter naming a value nothing matches contributes an empty page rather
        than a failure. The order is `created_at` descending, then `id`, so two
        plans written in the same transaction — a roadmap and its week — still come
        back in a defined order.
        """
        ...

    def find_study_plan(self, study_plan_id: uuid.UUID) -> StudyPlanRecord | None:
        """The plan with this identifier, or None.

        Ownership is deliberately not filtered here. Whether a plan belongs to the
        effective learner is a rule, so the use case decides it — the same
        division `find_study_goal` makes.
        """
        ...

    def list_active_study_plans(self, study_goal_id: uuid.UUID) -> tuple[StudyPlanRecord, ...]:
        """Every `active` plan belonging to this goal, in no particular order.

        Generation reads this to supersede what it replaces. A goal may hold more
        than one — a roadmap and a week are generated together — so this returns a
        collection rather than the single plan a first reading might expect.
        """
        ...

    def add_study_plan(self, record: StudyPlanRecord) -> None:
        """Store a new study plan."""
        ...

    def update_study_plan(self, record: StudyPlanRecord) -> None:
        """Overwrite the stored plan identified by ``record.id``."""
        ...

    def count_plan_items(self, study_plan_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        """How many items each plan named holds, keyed by plan identifier.

        Every identifier is asked for at once so listing a page of plans stays one
        query rather than one per plan. A plan with no items is absent from the
        result rather than present with a zero, which is what a `dict.get` default
        is for.
        """
        ...

    def list_plan_items(self, study_plan_id: uuid.UUID) -> tuple[PlanItemRecord, ...]:
        """Every item of one plan, in no particular order.

        One plan at a time, unlike the counts above: items are read only when a
        single plan is being returned, so there is no page of plans to spread the
        query across.
        """
        ...

    def find_plan_item(self, plan_item_id: uuid.UUID) -> PlanItemRecord | None:
        """The item with this identifier, or None.

        Ownership is deliberately not filtered here, as `find_study_plan` does
        not filter it: whether the item's plan belongs to the effective learner
        is a rule, so the use case decides it.
        """
        ...

    def add_plan_item(self, record: PlanItemRecord) -> None:
        """Store a new plan item.

        The item's plan must already have been sent to the store — see
        `flush` — because an item references its plan by foreign key.
        """
        ...

    def update_plan_item(self, record: PlanItemRecord) -> None:
        """Overwrite the stored item identified by ``record.id``.

        Only `status` and `completed_at` are ever different: PLN-004 is the one
        caller, and what a plan recommended is not rewritten by a learner acting
        on it. The whole record is passed anyway, matching `update_study_plan`,
        so the port stays a storage primitive rather than growing a method per
        column.
        """
        ...

    def flush(self) -> None:
        """Send pending writes to the store without ending the transaction.

        The use case calls this where one statement must land before the next,
        which the store cannot infer: a plan item references its plan, so the
        plan's INSERT has to reach the database first. `CurriculumSeedRepository`
        offers the same primitive for the same reason.

        It is **not** a commit. The caller still owns the transaction, so a
        generation that flushes a plan and then fails writes nothing at all.
        """
        ...

    def list_subjects(self, curriculum_version_id: uuid.UUID) -> tuple[SubjectRecord, ...]:
        """Every subject of this version, so an item can name where its topic sits."""
        ...

    def list_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[TopicRecord, ...]:
        """The topics named, in no particular order.

        Every identifier is asked for at once so returning a plan's items stays one
        query rather than one per item. An identifier naming no stored topic is
        absent from the result — which a re-seeded curriculum cannot cause, because
        the seed never deletes (ADR-012).
        """
        ...
