"""Request and response schemas for the study-plan endpoints (PLN-001 to PLN-005).

No request accepts a `learner_id`: the effective learner is resolved server-side
(docs/api/conventions.md). Generation names the *goal* to plan for, because a
learner may hold several, and whether that goal is theirs is decided by the use
case.

A plan reports the reason it exists and every item the reason it is there. Those
sentences are written when the plan is generated and never rewritten, so a
superseded plan still explains itself in the terms that produced it, which is what
FR-003 asks of a recommendation.

A listed plan carries no items and a read plan does. A page of plans each holding
every item would be an unbounded payload inside a paginated one, which the
pagination block in docs/api/conventions.md cannot describe; `item_count` says how
large a listed plan is.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.application.dto.study_plan import (
    PLAN_ITEM_ACTIONS,
    PLAN_ITEM_STATUS_CHANGES,
    PLAN_ITEM_STATUSES,
    PLAN_STATUSES,
    PLAN_TYPES,
    AdaptedStudyPlans,
    GeneratedStudyPlans,
    PlanFeasibility,
    PlanGenerationRequest,
    PlanItemDetail,
    PlanItemStatusChange,
    PlanItemTopic,
    StudyPlanDetail,
    StudyPlanPage,
)
from app.presentation.api.schemas.pagination import Pagination


class PlanItemTopicSchema(BaseModel):
    """The topic a plan item recommends work on."""

    id: uuid.UUID
    code: str | None
    name: str
    subject_id: uuid.UUID
    subject_name: str = Field(
        description="The subject the topic belongs to, so a plan reads without the whole tree."
    )

    @classmethod
    def of(cls, topic: PlanItemTopic) -> PlanItemTopicSchema:
        """Build the schema from its application DTO."""
        return cls(
            id=topic.id,
            code=topic.code,
            name=topic.name,
            subject_id=topic.subject_id,
            subject_name=topic.subject_name,
        )


class PlanItemSchema(BaseModel):
    """One recommended action within a plan."""

    id: uuid.UUID
    topic: PlanItemTopicSchema | None = Field(
        description="Null only for an item recommending work belonging to no single topic."
    )
    action_type: str = Field(description=f"One of: {', '.join(PLAN_ITEM_ACTIONS)}.")
    scheduled_for: date | None = Field(
        description=(
            "The day this work is recommended for. Null on a roadmap item, which says what "
            "order to work in rather than which day to do it on."
        )
    )
    estimated_minutes: int | None = Field(
        description=(
            "How long this item is expected to take. It is the learner's preferred session "
            "length, or what remains of a day too short to hold a whole session."
        )
    )
    priority: int = Field(
        description=(
            "Where this item falls in its plan, counting from 1. An order, not a score: "
            "nothing here ranks one topic above another by anything but position."
        )
    )
    status: str = Field(
        description=(
            f"One of: {', '.join(PLAN_ITEM_STATUSES)}. Generation writes `planned`; PLN-004 "
            "moves an item between `planned` and `completed`."
        )
    )
    recommendation_reason: str | None = Field(
        description="Why this item is here, as written when the plan was generated."
    )
    completed_at: datetime | None = Field(
        description=(
            "When the learner marked this item completed. Null unless `status` is `completed`, "
            "and cleared when an item is put back to `planned`."
        )
    )

    @classmethod
    def of(cls, item: PlanItemDetail) -> PlanItemSchema:
        """Build the schema from its application DTO."""
        return cls(
            id=item.id,
            topic=None if item.topic is None else PlanItemTopicSchema.of(item.topic),
            action_type=item.action_type,
            scheduled_for=item.scheduled_for,
            estimated_minutes=item.estimated_minutes,
            priority=item.priority,
            status=item.status,
            recommendation_reason=item.recommendation_reason,
            completed_at=item.completed_at,
        )


class StudyPlanSchema(BaseModel):
    """One study plan, with its items when a single plan was asked for."""

    id: uuid.UUID
    learner_id: uuid.UUID
    study_goal_id: uuid.UUID
    plan_type: str = Field(
        description=(
            f"One of: {', '.join(PLAN_TYPES)}. Generation produces a `roadmap` and, when the "
            "learner has saved study time the coming week can use, a `weekly` plan."
        )
    )
    period_start: date | None = Field(description="First day the plan covers.")
    period_end: date | None = Field(
        description=(
            "Last day the plan covers. On a roadmap this is the goal's horizon — the earlier "
            "of the examination window's first sitting day and the target date. Null only "
            "when the goal has neither, which `generation_reason` then states."
        )
    )
    status: str = Field(
        description=(
            f"One of: {', '.join(PLAN_STATUSES)}. Generating again sets the goal's existing "
            "`active` plans to `superseded` rather than deleting them."
        )
    )
    generation_reason: str | None = Field(
        description="Why this plan looks the way it does, as written when it was generated."
    )
    item_count: int = Field(description="How many items the plan holds, whether or not listed.")
    items: list[PlanItemSchema] = Field(
        description=(
            "The plan's items in plan order. Empty on a listed plan: read one plan to get "
            "its items."
        )
    )

    @classmethod
    def of(cls, plan: StudyPlanDetail) -> StudyPlanSchema:
        """Build the schema from its application DTO."""
        return cls(
            id=plan.id,
            learner_id=plan.learner_id,
            study_goal_id=plan.study_goal_id,
            plan_type=plan.plan_type,
            period_start=plan.period_start,
            period_end=plan.period_end,
            status=plan.status,
            generation_reason=plan.generation_reason,
            item_count=plan.item_count,
            items=[PlanItemSchema.of(item) for item in plan.items],
        )


class StudyPlanResponse(BaseModel):
    """One study plan, under the documented `data` envelope."""

    data: StudyPlanSchema


class StudyPlanCollectionResponse(BaseModel):
    """A page of study plans, under the documented collection envelope."""

    data: list[StudyPlanSchema]
    pagination: Pagination

    @classmethod
    def of(cls, page: StudyPlanPage) -> StudyPlanCollectionResponse:
        """Build the response from its application DTO."""
        return cls(
            data=[StudyPlanSchema.of(plan) for plan in page.plans],
            pagination=Pagination(limit=page.limit, offset=page.offset, total=page.total),
        )


class GenerateStudyPlanRequest(BaseModel):
    """A learner asking for a plan to be generated.

    Only the goal is named. Everything else a plan is built from — the
    curriculum, the horizon, the saved week, the planning preferences, and the
    recorded stages — is read from what the learner has already stored, so a
    client cannot pass a preference the learner did not set.
    """

    model_config = ConfigDict(extra="forbid")

    study_goal_id: uuid.UUID = Field(description="The goal to plan for.")

    def to_generation_request(self) -> PlanGenerationRequest:
        """Map the request onto the application's generation structure."""
        return PlanGenerationRequest(study_goal_id=self.study_goal_id)


class GeneratedStudyPlansSchema(BaseModel):
    """What one generation produced."""

    study_goal_id: uuid.UUID
    generated_on: date = Field(
        description=(
            "The date the plan was built around, in the learner's own timezone rather than "
            "the server's."
        )
    )
    plans: list[StudyPlanSchema] = Field(
        description=(
            "The plans written, each with its items. A roadmap always; a week when one fits."
        )
    )
    superseded_plan_ids: list[uuid.UUID] = Field(
        description=(
            "The plans this generation set aside. They are kept, not deleted, so an earlier "
            "plan can still be read."
        )
    )

    @classmethod
    def of(cls, generated: GeneratedStudyPlans) -> GeneratedStudyPlansSchema:
        """Build the schema from its application DTO."""
        return cls(
            study_goal_id=generated.study_goal_id,
            generated_on=generated.generated_on,
            plans=[StudyPlanSchema.of(plan) for plan in generated.plans],
            superseded_plan_ids=list(generated.superseded_plan_ids),
        )


class GenerateStudyPlanResponse(BaseModel):
    """A generated plan, under the documented `data` envelope.

    An object rather than a bare array, per ADR-014, and with no `pagination`
    block: one generation writes a known handful of plans belonging to one goal,
    so there is no window to page through.
    """

    data: GeneratedStudyPlansSchema


class UpdatePlanItemRequest(BaseModel):
    """A learner saying what became of one plan item (PLN-004).

    Only the status is accepted. `completed_at` is the server's record of when
    the learner said so, so taking one from a client would let a caller backdate
    work; an unknown field is rejected rather than ignored, as generation
    rejects one. Postponing takes no date — the work moves to the plan the next
    adaptation writes, not to a day named here. Neither skipping nor postponing
    takes a reason: nothing stores one, and asking for one would invite the
    product to form a view about the answer.
    """

    model_config = ConfigDict(extra="forbid")

    status: str = Field(
        description=(
            f"One of: {', '.join(PLAN_ITEM_STATUS_CHANGES)}. Every one is reversible while "
            "the item's plan is active. `postponed` is also written by adaptation (PLN-005) "
            "for work whose day passed with nothing said about it."
        )
    )

    def to_change(self) -> PlanItemStatusChange:
        """Map the request onto the application's status-change structure."""
        return PlanItemStatusChange(status=self.status)


class PlanItemResponse(BaseModel):
    """One plan item, under the documented `data` envelope.

    The whole item is returned rather than the status alone, so a client can
    re-render the line it just changed without reading the plan back.
    """

    data: PlanItemSchema


class AdaptedStudyPlansSchema(BaseModel):
    """What one adaptation produced."""

    study_goal_id: uuid.UUID
    adapted_on: date = Field(
        description=(
            "The date the adapted plan was built around, in the learner's own timezone "
            "rather than the server's."
        )
    )
    plans: list[StudyPlanSchema] = Field(
        description=(
            "The plans written, each with its items. A roadmap always; a week when one fits."
        )
    )
    superseded_plan_ids: list[uuid.UUID] = Field(
        description=(
            "The plans this adaptation set aside. They are kept, not deleted, so what was "
            "planned before can still be read."
        )
    )
    postponed_plan_item_ids: list[uuid.UUID] = Field(
        description=(
            "Items whose day had passed with the work undone. They are marked `postponed` on "
            "the plan being set aside, and their topics are planned again on the new one."
        )
    )
    completed_topic_count: int = Field(
        description=(
            "How many topics have a completed session on this goal and are therefore not "
            "planned again. A description of the plan, not a score for the learner."
        )
    )
    remaining_topic_count: int = Field(description="How many topics the adapted plan still covers.")

    @classmethod
    def of(cls, adapted: AdaptedStudyPlans) -> AdaptedStudyPlansSchema:
        """Build the schema from its application DTO."""
        return cls(
            study_goal_id=adapted.study_goal_id,
            adapted_on=adapted.adapted_on,
            plans=[StudyPlanSchema.of(plan) for plan in adapted.plans],
            superseded_plan_ids=list(adapted.superseded_plan_ids),
            postponed_plan_item_ids=list(adapted.postponed_plan_item_ids),
            completed_topic_count=adapted.completed_topic_count,
            remaining_topic_count=adapted.remaining_topic_count,
        )


class AdaptStudyPlanResponse(BaseModel):
    """An adapted plan, under the documented `data` envelope."""

    data: AdaptedStudyPlansSchema


class PlanFeasibilitySchema(BaseModel):
    """Whether the learner's saved week reaches their goal's horizon."""

    study_goal_id: uuid.UUID
    assessed_on: date = Field(
        description=(
            "The learner's own date this was assessed for, from their stored timezone "
            "rather than the server's. The answer depends on it."
        )
    )
    verdict: str = Field(
        description=(
            "`sufficient`, `insufficient`, or `unknown`. `unknown` is an answer, not a "
            "failure: some questions cannot be answered honestly from what is stored."
        )
    )
    reason: str = Field(
        description=(
            "The sentence a learner reads. It describes the plan and the time, never the "
            "learner, and states counts and durations rather than ratios."
        )
    )
    unknown_reason: str | None = Field(
        default=None,
        description=(
            "`no_horizon` when the goal aims at no examination cycle and no target date, "
            "`no_availability_saved` when no study week is stored. Null unless the verdict "
            "is `unknown`. A week saved and deliberately kept free is neither -- that is "
            "zero minutes, which is an answer."
        ),
    )
    horizon_ends_on: date | None = Field(
        default=None,
        description=(
            "The date the work has to be done by: the earlier of the examination window's "
            "first sitting day and the goal's target date. Null when the goal aims at neither."
        ),
    )
    remaining_topic_count: int = Field(
        description=(
            "Topics on the active roadmap that still have work. A completed topic is not "
            "one; a skipped or postponed one is, because the next plan places its work again."
        )
    )
    session_minutes: int = Field(description="How long one session was taken to run.")
    session_minutes_chosen_by_planner: bool = Field(
        description=(
            "True when the learner has set no session length and LearnFlow chose one for "
            "itself. Reported so a screen can say whose decision it was, never presenting "
            "an unset preference as a default the learner made."
        )
    )
    study_days: int = Field(
        description=(
            "Calendar days from `assessed_on` to the horizon, both ends included. Zero when "
            "the horizon has passed."
        )
    )
    available_minutes: int = Field(description="What the saved week offers across those days.")
    required_minutes: int = Field(description="One session for each remaining topic.")
    shortfall_minutes: int = Field(
        description=(
            "How much more time the work needs than the week offers. Zero when the week is "
            "enough, and never negative -- a surplus is reported by the verdict instead."
        )
    )
    coverable_topic_count: int = Field(
        description=(
            "How many remaining topics the available time holds a whole session for. Stated "
            "beside `remaining_topic_count` as two counts; never rendered as one over the "
            "other, because a ratio invites a comparison this contract refuses to make."
        )
    )

    @classmethod
    def of(cls, feasibility: PlanFeasibility) -> PlanFeasibilitySchema:
        """Build the schema from its application DTO."""
        return cls(
            study_goal_id=feasibility.study_goal_id,
            assessed_on=feasibility.assessed_on,
            verdict=feasibility.verdict,
            reason=feasibility.reason,
            unknown_reason=feasibility.unknown_reason,
            horizon_ends_on=feasibility.horizon_ends_on,
            remaining_topic_count=feasibility.remaining_topic_count,
            session_minutes=feasibility.session_minutes,
            session_minutes_chosen_by_planner=feasibility.session_minutes_chosen_by_planner,
            study_days=feasibility.study_days,
            available_minutes=feasibility.available_minutes,
            required_minutes=feasibility.required_minutes,
            shortfall_minutes=feasibility.shortfall_minutes,
            coverable_topic_count=feasibility.coverable_topic_count,
        )


class PlanFeasibilityResponse(BaseModel):
    """A feasibility assessment, under the documented `data` envelope."""

    data: PlanFeasibilitySchema
