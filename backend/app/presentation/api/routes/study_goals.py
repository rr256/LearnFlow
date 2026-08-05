"""Study goal endpoints (GOAL-001 to GOAL-004).

They serve the second half of FR-002: the learner confirms the learning program
they are studying and what they are working toward -- a published examination
cycle, a target completion date, or both.

Every route here is thin: validate, call the use case, map the result or its
error to a documented response. No route touches a session, a model, or a query
(docs/architecture/dependency-rules.md).

No route accepts a learner identifier. The effective learner is resolved
server-side, so a request cannot read or write another learner's goals
(docs/api/conventions.md).

GOAL-005 is not implemented. Replacing weekly availability needs
`availability_slots`, which does not exist: creating it would fix the
`day_of_week` numbering convention that ADR-011 keeps open until a requirement
constrains it.
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

from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_study_goals import (
    ActiveGoalExistsError,
    EmptyGoalUpdateError,
    LearnerNotSetUpError,
    ManageStudyGoals,
    MissingGoalTargetError,
    StudyGoalNotFoundError,
    UnknownGoalStatusError,
    UnknownReferenceError,
)
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_study_goals
from app.presentation.api.errors import ErrorDetail, ErrorResponse, RequestRejected
from app.presentation.api.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.presentation.api.schemas.study_goal import (
    CreateStudyGoalRequest,
    StudyGoalCollectionResponse,
    StudyGoalResponse,
    StudyGoalSchema,
    UpdateStudyGoalRequest,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/study-goals", tags=["study-goals"])

_NOT_FOUND_RESPONSE = {HTTP_404_NOT_FOUND: {"model": ErrorResponse}}
_CONFLICT_RESPONSE = {HTTP_409_CONFLICT: {"model": ErrorResponse}}
_WRITE_RESPONSES = _NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE

StudyGoalManager = Annotated[ManageStudyGoals, Depends(provide_study_goals)]


@router.post(
    "",
    summary="Create a study goal",
    response_model=StudyGoalResponse,
    status_code=HTTP_201_CREATED,
    responses=_CONFLICT_RESPONSE,
)
def create_study_goal(
    request: CreateStudyGoalRequest, goals: StudyGoalManager
) -> StudyGoalResponse:
    """Create a goal for a program, aiming at an examination cycle, a date, or both.

    The goal binds to the program's active curriculum version. A second create
    for a program the learner already has an active goal for is a `409`: the
    existing goal is what any plan was built from, so a repeated form submission
    must not replace it. Edit through GOAL-004 instead.

    GOAL-001. Serves FR-002.
    """
    try:
        goal = goals.create(request.to_new_study_goal())
    except MissingGoalTargetError as error:
        raise _missing_target(error) from error
    except UnknownReferenceError as error:
        raise _unknown_reference(error) from error
    except (LearnerNotSetUpError, ActiveGoalExistsError, AmbiguousLocalLearnerError) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return StudyGoalResponse(data=StudyGoalSchema.of(goal))


@router.get(
    "",
    summary="List the learner's study goals",
    response_model=StudyGoalCollectionResponse,
    responses=_CONFLICT_RESPONSE,
)
def list_study_goals(
    goals: StudyGoalManager,
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_PAGE_SIZE, description="Maximum number of goals to return."),
    ] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, description="Number of goals to skip.")] = 0,
) -> StudyGoalCollectionResponse:
    """Read the local learner's study goals, newest first.

    An installation where setup has not run yet has no learner and therefore no
    goals, which is an empty page rather than a failure.

    GOAL-002. Serves FR-002.
    """
    try:
        page = goals.list_study_goals(limit=limit, offset=offset)
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return StudyGoalCollectionResponse.of(page)


@router.get(
    "/{study_goal_id}",
    summary="Read one study goal",
    response_model=StudyGoalResponse,
    responses=_WRITE_RESPONSES,
)
def read_study_goal(study_goal_id: uuid.UUID, goals: StudyGoalManager) -> StudyGoalResponse:
    """Read one of the local learner's goals.

    A goal belonging to somebody else is reported as missing rather than
    forbidden: `docs/api/conventions.md` treats "not visible to the caller" as a
    `404`, and saying otherwise would confirm a record the caller may not read.

    No availability summary is returned; `availability_slots` does not exist yet.

    GOAL-003. Serves FR-002.
    """
    try:
        goal = goals.read(study_goal_id)
    except StudyGoalNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return StudyGoalResponse(data=StudyGoalSchema.of(goal))


@router.patch(
    "/{study_goal_id}",
    summary="Update a study goal",
    response_model=StudyGoalResponse,
    responses=_WRITE_RESPONSES,
)
def update_study_goal(
    study_goal_id: uuid.UUID, request: UpdateStudyGoalRequest, goals: StudyGoalManager
) -> StudyGoalResponse:
    """Change a goal's examination cycle, target date, or status.

    A field the request omits is left alone; an explicit null clears it. The
    result must still aim at an examination cycle, a target date, or both.

    Planning preferences are not accepted: the column does not exist, so the
    field would promise storage the database has not got.

    GOAL-004. Serves FR-002.
    """
    try:
        goal = goals.update(study_goal_id, request.to_changes())
    except StudyGoalNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except MissingGoalTargetError as error:
        raise _missing_target(error) from error
    except UnknownReferenceError as error:
        raise _unknown_reference(error) from error
    except EmptyGoalUpdateError as error:
        raise RequestRejected(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
            details=[ErrorDetail(field="body", message=str(error), type="empty_update")],
        ) from error
    except UnknownGoalStatusError as error:
        raise RequestRejected(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
            details=[ErrorDetail(field="body.status", message=str(error), type="unknown_status")],
        ) from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return StudyGoalResponse(data=StudyGoalSchema.of(goal))


def _missing_target(error: MissingGoalTargetError) -> RequestRejected:
    """Report the two fields either of which would give the goal a horizon."""
    message = str(error)
    return RequestRejected(
        status_code=HTTP_422_UNPROCESSABLE_CONTENT,
        detail=message,
        details=[
            ErrorDetail(field=f"body.{name}", message=message, type="missing_goal_target")
            for name in ("examination_schedule_id", "target_date")
        ],
    )


def _unknown_reference(error: UnknownReferenceError) -> RequestRejected:
    """Report the request field naming a record that is not stored."""
    message = str(error)
    return RequestRejected(
        status_code=HTTP_422_UNPROCESSABLE_CONTENT,
        detail=message,
        details=[
            ErrorDetail(field=f"body.{error.field}", message=message, type="unknown_reference")
        ],
    )
