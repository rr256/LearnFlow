"""Plan item endpoint (PLN-004).

It serves the whole of FR-004's first acceptance criterion — a learner marking a
planned task completed, skipped, or postponed — between itself and PLN-005. This
route takes the two statements a learner makes about their own work, `completed`
and `skipped`, and the `planned` that takes either back. `postponed` is the one
adaptation writes as it sets a plan aside, so it is refused here rather than
requested.

The route sits at its own prefix rather than under `/study-plans`, as
docs/api/endpoints.md catalogues it: an item is addressed by its own identifier,
and a learner acting on one line of a plan should not have to name the plan it
came from.

The route is thin: validate, call the use case, map the result or its error to a
documented response. It touches no session, no model, and no query
(docs/architecture/dependency-rules.md), and it holds no rule about which status
a learner may ask for — that is decided in `ManageStudyPlans`.

No route here accepts a learner identifier. The effective learner is resolved
server-side, so a request cannot complete another learner's plan item
(docs/api/conventions.md).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import (
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_CONTENT,
)

from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_study_plans import (
    LearnerNotSetUpError,
    ManageStudyPlans,
    PlanItemNotFoundError,
    PlanItemNotOnActivePlanError,
    UnknownPlanItemStatusError,
)
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_study_plans
from app.presentation.api.errors import ErrorDetail, ErrorResponse, RequestRejected
from app.presentation.api.schemas.study_plan import (
    PlanItemResponse,
    PlanItemSchema,
    UpdatePlanItemRequest,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/plan-items", tags=["study-plans"])

_NOT_FOUND_RESPONSE = {HTTP_404_NOT_FOUND: {"model": ErrorResponse}}
_CONFLICT_RESPONSE = {HTTP_409_CONFLICT: {"model": ErrorResponse}}

StudyPlanner = Annotated[ManageStudyPlans, Depends(provide_study_plans)]


@router.patch(
    "/{plan_item_id}",
    summary="Mark a plan item completed or skipped, or return it to planned",
    response_model=PlanItemResponse,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def update_plan_item(
    plan_item_id: uuid.UUID, request: UpdatePlanItemRequest, planner: StudyPlanner
) -> PlanItemResponse:
    """Record what became of one item's planned work.

    Marking an item `completed` says its planned work happened. Marking it
    `skipped` says the learner decided it would not. Neither is a claim that the
    topic is understood: a learning stage is the learner's own statement and is
    recorded separately, through PRG-004.

    Every move is reversible. A learner who marked the wrong line can send
    `planned` to put it back, which clears the completion time, and may move
    straight between `completed` and `skipped`. Nothing here treats a statement
    about work as a verdict, so nothing here is one-way.

    Skipping settles the item, not the topic. The item stays skipped, adaptation
    will not carry it forward as `postponed`, and the topic is planned again on
    the plan that replaces this one.

    Sending the status an item already holds is accepted and writes nothing, so a
    repeated submission does not fail on its second attempt.

    An item on a superseded plan is refused with a `409`: a replaced plan is kept
    as a record of what was planned, and reads exactly as it was written.

    Nothing else moves. No other item changes, no plan is re-planned, and no topic
    progress is written — re-planning is PLN-005, which the learner asks for.

    PLN-004. Serves FR-004.
    """
    try:
        item = planner.record_item_status(plan_item_id, request.to_change())
    except PlanItemNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except UnknownPlanItemStatusError as error:
        raise RequestRejected(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
            details=[
                ErrorDetail(
                    field="body.status", message=str(error), type="unknown_plan_item_status"
                )
            ],
        ) from error
    except (
        LearnerNotSetUpError,
        PlanItemNotOnActivePlanError,
        AmbiguousLocalLearnerError,
    ) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return PlanItemResponse(data=PlanItemSchema.of(item))
