"""Topic-progress endpoints (PRG-002, PRG-004).

They serve the manual half of FR-005: a learner records how far along they are
with a topic, changes it later, and reads back what they recorded.

Every route here is thin: validate, call the use case, map the result or its
error to a documented response. No route touches a session, a model, or a query
(docs/architecture/dependency-rules.md).

Neither route accepts a learner identifier. The effective learner is resolved
server-side, so no request can read or write another learner's progress
(docs/api/conventions.md).

The rest of the progress surface is not implemented. PRG-001 needs the plan,
revisions, and priority focus areas that Milestone 3 brings; PRG-003 reports
evidence and a next action that nothing yet produces; ACT-001 and ACT-002 need
`study_activities`, which does not exist. Each arrives with the code that can
fill it, rather than as a contract fixed ahead of its first caller.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.status import (
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_CONTENT,
)

from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_topic_progress import (
    LearnerNotSetUpError,
    ManageTopicProgress,
    TopicNotFoundError,
    TopicNotTrackableError,
    UnknownLearningStageError,
)
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_topic_progress
from app.presentation.api.errors import ErrorDetail, ErrorResponse, RequestRejected
from app.presentation.api.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.presentation.api.schemas.topic_progress import (
    RecordTopicStageRequest,
    TopicProgressCollectionResponse,
    TopicProgressResponse,
    TopicProgressSchema,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/progress", tags=["progress"])

_NOT_FOUND_RESPONSE = {HTTP_404_NOT_FOUND: {"model": ErrorResponse}}
_CONFLICT_RESPONSE = {HTTP_409_CONFLICT: {"model": ErrorResponse}}

TopicProgressManager = Annotated[ManageTopicProgress, Depends(provide_topic_progress)]


@router.get(
    "/topics",
    summary="List the learner's recorded topic progress",
    response_model=TopicProgressCollectionResponse,
    responses=_CONFLICT_RESPONSE,
)
def list_topic_progress(
    progress: TopicProgressManager,
    curriculum_version_id: Annotated[
        uuid.UUID | None,
        Query(description="Restrict to topics of one curriculum version."),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_PAGE_SIZE, description="Maximum number of records to return."),
    ] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, description="Number of records to skip.")] = 0,
) -> TopicProgressCollectionResponse:
    """Read the stages the local learner has recorded, newest first.

    Only topics with a stored record appear. A topic that is absent has no
    recorded stage, which reads as *Not explored* -- the neutral starting state.
    Listing every topic is what the curriculum endpoints do; a client showing
    both joins them by topic identifier.

    An installation where setup has not run has no learner and therefore no
    records, which is an empty page rather than a failure. A
    `curriculum_version_id` that is not stored matches nothing, which is likewise
    an empty page rather than a `404`.

    PRG-002. Serves FR-005.
    """
    try:
        page = progress.list_topic_progress(
            curriculum_version_id=curriculum_version_id, limit=limit, offset=offset
        )
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return TopicProgressCollectionResponse.of(page)


@router.patch(
    "/topics/{topic_id}",
    summary="Record the learner's learning stage for a topic",
    response_model=TopicProgressResponse,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def record_topic_stage(
    topic_id: uuid.UUID, request: RecordTopicStageRequest, progress: TopicProgressManager
) -> TopicProgressResponse:
    """Record or change the learning stage for one topic.

    The record comes into existence on the learner's own action, as the learner
    profile does. A learner may move to any stage from any stage, including
    backwards: noticing that a topic needs more work is worth recording, and
    nothing here treats the five stages as a score.

    Recording the stage a topic already holds is accepted and writes nothing, so
    a repeated form submission does not fail on its second attempt.

    A topic that only groups subtopics is refused with a `422`: `is_trackable`
    says whether progress can be recorded directly, and a grouping heading
    cannot hold a stage of its own.

    PRG-004. Serves FR-005.
    """
    try:
        detail = progress.record_stage(topic_id, request.to_change())
    except TopicNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except UnknownLearningStageError as error:
        raise RequestRejected(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
            details=[
                ErrorDetail(
                    field="body.learning_stage",
                    message=str(error),
                    type="unknown_learning_stage",
                )
            ],
        ) from error
    except TopicNotTrackableError as error:
        raise RequestRejected(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
            details=[
                ErrorDetail(field="path.topic_id", message=str(error), type="topic_not_trackable")
            ],
        ) from error
    except (LearnerNotSetUpError, AmbiguousLocalLearnerError) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return TopicProgressResponse(data=TopicProgressSchema.of(detail))
