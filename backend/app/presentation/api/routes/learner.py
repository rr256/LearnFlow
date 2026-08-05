"""Learner profile endpoints (LRN-001, LRN-002).

They serve the first half of FR-002: a learner establishes who they are and the
timezone their study dates are read in, before any goal is set.

Every route here is thin: validate, call the use case, map the result or its
error to a documented response. No route touches a session, a model, or a query
(docs/architecture/dependency-rules.md).

Neither route accepts a learner identifier. The effective learner is resolved
server-side, so no request can address another learner's profile
(docs/api/conventions.md).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import HTTP_409_CONFLICT, HTTP_422_UNPROCESSABLE_CONTENT

from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_learner_profile import (
    EmptyProfileUpdateError,
    ManageLearnerProfile,
)
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_learner_profile
from app.presentation.api.errors import ErrorDetail, ErrorResponse, RequestRejected
from app.presentation.api.schemas.learner import (
    LearnerProfileResponse,
    LearnerProfileSchema,
    LearnerProfileUpdateRequest,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/learner", tags=["learner"])

_CONFLICT_RESPONSE = {HTTP_409_CONFLICT: {"model": ErrorResponse}}

LearnerProfileManager = Annotated[ManageLearnerProfile, Depends(provide_learner_profile)]


@router.get(
    "/profile",
    summary="Read the local learner's profile",
    response_model=LearnerProfileResponse,
    responses=_CONFLICT_RESPONSE,
)
def read_learner_profile(profiles: LearnerProfileManager) -> LearnerProfileResponse:
    """Read the local learner's profile and preferences.

    Returns `data: null` when setup has not created a learner yet. That is a real
    state of a fresh installation, not a failure, and a read never creates the
    record it did not find.

    LRN-001. Serves FR-002.
    """
    try:
        profile = profiles.read()
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return LearnerProfileResponse(
        data=None if profile is None else LearnerProfileSchema.of(profile)
    )


@router.patch(
    "/profile",
    summary="Update the local learner's profile",
    response_model=LearnerProfileResponse,
    responses=_CONFLICT_RESPONSE,
)
def update_learner_profile(
    request: LearnerProfileUpdateRequest, profiles: LearnerProfileManager
) -> LearnerProfileResponse:
    """Update the learner's display name or timezone, creating the learner if needed.

    This is where the local learner record comes into existence, on the learner's
    own action. A field the request omits is left alone; `display_name: null`
    removes the stored name.

    LRN-002. Serves FR-002.
    """
    try:
        profile = profiles.update(request.to_changes())
    except EmptyProfileUpdateError as error:
        raise RequestRejected(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
            details=[
                ErrorDetail(
                    field="body",
                    message=str(error),
                    type="empty_update",
                )
            ],
        ) from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return LearnerProfileResponse(data=LearnerProfileSchema.of(profile))
