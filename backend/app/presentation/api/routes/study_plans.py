"""Study plan endpoints (PLN-001 to PLN-003).

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

PLN-004 and PLN-005 — completing a plan item and re-planning after missed work —
are FR-004 and are not implemented. Nothing here moves an item's status.
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
    StudyGoalNotFoundError,
    StudyPlanNotFoundError,
    UnknownPlanFilterError,
)
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_study_plans
from app.presentation.api.errors import ErrorDetail, ErrorResponse, RequestRejected
from app.presentation.api.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.presentation.api.schemas.study_plan import (
    GeneratedStudyPlansSchema,
    GenerateStudyPlanRequest,
    GenerateStudyPlanResponse,
    StudyPlanCollectionResponse,
    StudyPlanResponse,
    StudyPlanSchema,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/study-plans", tags=["study-plans"])

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
