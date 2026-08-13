"""Study plan endpoints (PLN-001 to PLN-003, and PLN-005).

They serve FR-002's last acceptance criterion — a learner with no previous
progress still receives an initial plan — and the first part of FR-003, which
asks for a roadmap toward the target date and recommendations the learner can see
the reasons for.

Every route here is thin: validate, call the use case, map the result or its error
to a documented response. No route touches a session, a model, or a query
(docs/architecture/dependency-rules.md), and no route contains a planning rule:
what order topics go in and which day each lands on are decided in
`app.domain.study_planning`.

No route accepts a learner identifier. The effective learner is resolved
server-side, so a request cannot read or generate against another learner's
records (docs/api/conventions.md).

PLN-004 — completing a plan item — lives beside these in `plan_items.py`, at its
own path, because it addresses one item rather than a plan.

PLN-005 is served here but sits under a **goal-scoped** path, on the second router
below: adaptation supersedes and rewrites every active plan of a goal, so a path
naming one plan would misdescribe what moves. **PLN-006 sits there too**, for the
same reason and one more: it reads the goal's horizon, its saved week, and its
preferences alongside the active plan, so the goal is what is being asked about.
It is the only route here that writes nothing at all.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_CONTENT,
)

from app.application.dto.study_plan import PLAN_STATUSES, PLAN_TYPES, StudyPlanFilters
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_study_plans import (
    LearnerNotSetUpError,
    ManageStudyPlans,
    NoActivePlanToAdaptError,
    StudyGoalNotFoundError,
    StudyPlanNotFoundError,
    UnknownPlanFilterError,
)
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_study_plans
from app.presentation.api.errors import ErrorDetail, ErrorResponse, RequestRejected
from app.presentation.api.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.presentation.api.schemas.study_plan import (
    AdaptedStudyPlansSchema,
    AdaptStudyPlanResponse,
    GeneratedStudyPlansSchema,
    GenerateStudyPlanRequest,
    GenerateStudyPlanResponse,
    PlanFeasibilityResponse,
    PlanFeasibilitySchema,
    StudyPlanCollectionResponse,
    StudyPlanResponse,
    StudyPlanSchema,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/study-plans", tags=["study-plans"])

goal_router = APIRouter(prefix=f"{API_V1_PREFIX}/study-goals", tags=["study-plans"])
"""Planning operations addressed by the goal rather than by one plan.

PLN-005 lives here because adaptation acts on a goal's whole active set — it
supersedes the roadmap and the week together and writes both — so
`/study-plans/{plan_id}/adapt` would name one plan while moving two. The router
is declared in this module rather than beside the goal endpoints because the
operation is planning work served by `ManageStudyPlans`.
"""

_NOT_FOUND_RESPONSE = {HTTP_404_NOT_FOUND: {"model": ErrorResponse}}
_CONFLICT_RESPONSE = {HTTP_409_CONFLICT: {"model": ErrorResponse}}

StudyPlanner = Annotated[ManageStudyPlans, Depends(provide_study_plans)]


@router.post(
    "/generate",
    summary="Generate a study plan for a goal",
    response_model=GenerateStudyPlanResponse,
    status_code=HTTP_201_CREATED,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def generate_study_plan(
    request: GenerateStudyPlanRequest, planner: StudyPlanner
) -> GenerateStudyPlanResponse:
    """Build an initial study plan from what the learner has already set up.

    The plan is deterministic: the same goal, curriculum, week, preferences, and
    date produce the same plan, with no AI provider involved. A roadmap orders
    every trackable topic across the goal's horizon, and a weekly plan dates the
    first of them onto the days the learner said they can study.

    Generating again supersedes the goal's existing active plans rather than
    refusing or duplicating, so a learner whose availability changed simply asks
    again. Nothing is deleted, and an earlier plan can still be read.

    A learner with no recorded progress still receives a plan, which is what
    FR-002's last acceptance criterion asks for.

    PLN-001. Serves FR-002 and FR-003.
    """
    try:
        generated = planner.generate(request.to_generation_request())
    except StudyGoalNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (LearnerNotSetUpError, AmbiguousLocalLearnerError) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return GenerateStudyPlanResponse(data=GeneratedStudyPlansSchema.of(generated))


@router.get(
    "",
    summary="List the learner's study plans",
    response_model=StudyPlanCollectionResponse,
    responses=_CONFLICT_RESPONSE,
)
def list_study_plans(
    planner: StudyPlanner,
    study_goal_id: Annotated[
        uuid.UUID | None, Query(description="Only plans belonging to this goal.")
    ] = None,
    plan_type: Annotated[str | None, Query(description=f"One of: {', '.join(PLAN_TYPES)}.")] = None,
    status: Annotated[str | None, Query(description=f"One of: {', '.join(PLAN_STATUSES)}.")] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_PAGE_SIZE, description="Maximum number of plans to return."),
    ] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, description="Number of plans to skip.")] = 0,
) -> StudyPlanCollectionResponse:
    """Read the local learner's plans, newest first.

    Items are not included: `item_count` says how large each plan is, and PLN-003
    returns the items of the one a client opens. A goal identifier that matches
    nothing is an empty page rather than a failure, while an unknown plan type or
    status is a `422` — the first is a filter matching no record, the second is a
    caller having misread the contract.

    An installation where setup has not run has no learner and therefore no plans,
    which is an empty page.

    PLN-002. Serves FR-003.
    """
    try:
        page = planner.list_study_plans(
            filters=StudyPlanFilters(
                study_goal_id=study_goal_id, plan_type=plan_type, status=status
            ),
            limit=limit,
            offset=offset,
        )
    except UnknownPlanFilterError as error:
        raise RequestRejected(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
            details=[
                ErrorDetail(
                    field=f"query.{error.field}", message=str(error), type="unknown_plan_filter"
                )
            ],
        ) from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return StudyPlanCollectionResponse.of(page)


@router.get(
    "/{study_plan_id}",
    summary="Read one study plan and its items",
    response_model=StudyPlanResponse,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def read_study_plan(study_plan_id: uuid.UUID, planner: StudyPlanner) -> StudyPlanResponse:
    """Read one of the local learner's plans, with its items in plan order.

    A plan belonging to somebody else is reported as missing rather than
    forbidden: `docs/api/conventions.md` treats "not visible to the caller" as a
    `404`, and saying otherwise would confirm a record the caller may not read.

    A superseded plan is readable, and reads exactly as it was written. That is
    the point of superseding rather than deleting.

    PLN-003. Serves FR-003.
    """
    try:
        plan = planner.read(study_plan_id)
    except StudyPlanNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return StudyPlanResponse(data=StudyPlanSchema.of(plan))


@goal_router.post(
    "/{study_goal_id}/adapt",
    summary="Adapt a goal's active study plan around what has happened",
    response_model=AdaptStudyPlanResponse,
    status_code=HTTP_201_CREATED,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def adapt_study_plan(study_goal_id: uuid.UUID, planner: StudyPlanner) -> AdaptStudyPlanResponse:
    """Rebuild the goal's active plans around completed and missed work.

    The learner asks for this. Nothing adapts on its own — not on completion, not
    on a changed study week — which keeps PLN-004's promise that marking an item
    done re-plans nothing.

    **Topics with a completed session are not planned again**, wherever on this
    goal they were completed, including on a plan long superseded. **Items whose
    day passed with the work undone are marked `postponed`** on the plan being set
    aside, and their topics are re-placed on the new one.

    Everything else is the plan PLN-001 would have built from the same curriculum,
    week, preferences, and horizon, by the same deterministic rules. No AI
    provider is involved, and the same inputs produce the same adapted plan.

    Takes no request body: everything adaptation reads is already stored, so no
    caller can adapt toward a preference the learner never set.

    A goal with no active plan is a `409` — generating a first plan is PLN-001's
    work, not this endpoint's.

    PLN-005. Serves FR-004.
    """
    try:
        adapted = planner.adapt(study_goal_id)
    except StudyGoalNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (
        LearnerNotSetUpError,
        NoActivePlanToAdaptError,
        AmbiguousLocalLearnerError,
    ) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return AdaptStudyPlanResponse(data=AdaptedStudyPlansSchema.of(adapted))


@goal_router.get(
    "/{study_goal_id}/plan-feasibility",
    summary="Report whether the saved study week reaches the goal's horizon",
    response_model=PlanFeasibilityResponse,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def read_plan_feasibility(
    study_goal_id: uuid.UUID, planner: StudyPlanner
) -> PlanFeasibilityResponse:
    """Say whether the learner's saved week can cover the work left before their date.

    **A reading. Nothing is written** — no plan, no availability, no preference,
    and no plan item status moves because this was asked, and nothing adapts. A
    learner may ask as often as they like, which is what keeps the answer current
    as they edit their week.

    The verdict is `sufficient`, `insufficient`, or `unknown`. **`unknown` is an
    answer**, with `unknown_reason` saying which gap caused it: a goal aiming at no
    date needs one, and a goal with no saved week needs a week. A week the learner
    saved and deliberately kept free is neither — that is zero minutes, which is a
    real answer.

    The arithmetic is deterministic and involves no AI provider: one session for
    each remaining topic, against the minutes the saved week offers on every day
    from today to the horizon, both ends included. Everything is reported as
    **counts and durations**; there is deliberately no percentage, ratio, or
    proportion, and no number here describes the learner.

    PLN-006. Serves FR-004's third acceptance criterion.
    """
    try:
        feasibility = planner.assess_feasibility(study_goal_id)
    except StudyGoalNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (LearnerNotSetUpError, AmbiguousLocalLearnerError) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return PlanFeasibilityResponse(data=PlanFeasibilitySchema.of(feasibility))
