"""Revision endpoints (REV-001 to REV-004).

They serve **FR-006 — Revision Guidance**: seeing the topics due for review,
recording what became of each one, and asking for the next round to be scheduled
from work already finished.

Every route here is thin: validate, call the use case, map the result or its
error to a documented response. No route touches a session, a model, or a query
(docs/architecture/dependency-rules.md), and no route contains a scheduling rule:
how long a topic waits and what counts as due are decided in
`app.domain.revision_scheduling`.

No route accepts a learner identifier. The effective learner is resolved
server-side, so a request cannot read or move another learner's revisions
(docs/api/conventions.md).

**REV-004 is not in the endpoint catalogue's original three.** Something has to
create a revision, and nothing may do it automatically: completing a plan item
writes no revision, because that would move a record the learner did not name.
So the learner asks, exactly as they ask for a plan to be generated or adapted.
ADR-028 records the departure, as ADR-022 recorded PLN-005's.
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

from app.application.dto.revision import REVISION_STATUSES, RevisionFilters
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_revisions import (
    LearnerNotSetUpError,
    ManageRevisions,
    RevisionNotFoundError,
    UnknownRevisionStatusError,
)
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_revisions
from app.presentation.api.errors import ErrorDetail, ErrorResponse, RequestRejected
from app.presentation.api.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.presentation.api.schemas.revision import (
    RevisionCollectionResponse,
    RevisionResponse,
    RevisionSchema,
    ScheduledRevisionsSchema,
    ScheduleRevisionsResponse,
    UpdateRevisionRequest,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/revisions", tags=["revisions"])

_NOT_FOUND_RESPONSE = {HTTP_404_NOT_FOUND: {"model": ErrorResponse}}
_CONFLICT_RESPONSE = {HTTP_409_CONFLICT: {"model": ErrorResponse}}

Reviser = Annotated[ManageRevisions, Depends(provide_revisions)]


@router.post(
    "/schedule",
    summary="Schedule revisions for topics whose finished work is ready to return",
    response_model=ScheduleRevisionsResponse,
    status_code=HTTP_201_CREATED,
    responses=_CONFLICT_RESPONSE,
)
def schedule_revisions(reviser: Reviser) -> ScheduleRevisionsResponse:
    """Bring finished topics back for review, on the learner's ask.

    **The learner asks; nothing schedules on its own.** Completing a plan item
    creates no revision and neither does completing a revision, so a list never
    rearranges itself under a learner who is working through it.

    A topic is brought back when they completed planned work on it, dated from
    when they finished and by an interval the learning stage they recorded
    decides — or by LearnFlow's own interval, named as its own, when they have
    recorded none. A topic whose last revision they **completed** comes back
    again, which is what makes review spaced.

    **Asking twice creates nothing the second time.** A topic with a revision
    already waiting is left alone, and so is one whose revision the learner
    skipped or postponed: they have said what became of that review, and this
    does not overrule them. `already_scheduled_topic_count` says how many were
    left as they are.

    Deterministic, with no AI provider: the same completed work, stages, and date
    produce the same revisions. Takes no request body — everything it reads is
    already stored.

    Nothing else moves: no plan, no plan item, and **no learning stage**, because
    a revision records whether a review happened rather than that a topic is
    understood.

    REV-004. Serves FR-006.
    """
    try:
        scheduled = reviser.schedule()
    except (LearnerNotSetUpError, AmbiguousLocalLearnerError) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return ScheduleRevisionsResponse(data=ScheduledRevisionsSchema.of(scheduled))


@router.get(
    "",
    summary="List the learner's revisions",
    response_model=RevisionCollectionResponse,
    responses=_CONFLICT_RESPONSE,
)
def list_revisions(
    reviser: Reviser,
    status: Annotated[
        str | None, Query(description=f"One of: {', '.join(REVISION_STATUSES)}.")
    ] = None,
    due_only: Annotated[bool, Query(description="Only revisions nobody has settled yet.")] = False,
    limit: Annotated[
        int, Query(ge=1, le=MAX_PAGE_SIZE, description="Maximum number of revisions to return.")
    ] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, description="Number of revisions to skip.")] = 0,
) -> RevisionCollectionResponse:
    """Read the local learner's revisions, earliest due date first.

    That order is the order a learner works through them, and it is fixed by the
    repository so a page cannot be reordered after it has been sliced.

    `is_due` on each record says whether it is owed today. An installation where
    setup has not run has no learner and therefore no revisions, which is an
    empty page rather than a failure. An unknown status is a `422` — a caller
    having misread the contract, rather than a filter matching nothing.

    REV-001. Serves FR-006.
    """
    try:
        page = reviser.list_revisions(
            filters=RevisionFilters(status=status, due_only=due_only),
            limit=limit,
            offset=offset,
        )
    except UnknownRevisionStatusError as error:
        raise RequestRejected(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
            details=[
                ErrorDetail(
                    field="query.status", message=str(error), type="unknown_revision_status"
                )
            ],
        ) from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return RevisionCollectionResponse.of(page, limit=limit, offset=offset)


@router.get(
    "/{revision_id}",
    summary="Read one revision and the topic it names",
    response_model=RevisionResponse,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def read_revision(revision_id: uuid.UUID, reviser: Reviser) -> RevisionResponse:
    """Read one of the learner's revisions.

    A revision owned by somebody else is reported as missing rather than
    forbidden, the rule every learner-owned read here follows: saying "that
    exists but is not yours" would confirm a record the caller may not read.

    REV-002. Serves FR-006.
    """
    try:
        revision = reviser.read(revision_id)
    except RevisionNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return RevisionResponse(data=RevisionSchema.of(revision))


@router.patch(
    "/{revision_id}",
    summary="Record what became of one revision",
    response_model=RevisionResponse,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def update_revision(
    revision_id: uuid.UUID, request: UpdateRevisionRequest, reviser: Reviser
) -> RevisionResponse:
    """Mark a revision completed, skipped, or postponed, or put it back to due.

    **Every move between the four is allowed**, from whichever the revision
    currently holds. Nothing is one-way: they are four answers to one question
    rather than a sequence, which is the position PLN-004 takes on a plan item
    and ADR-017 takes on a learning stage. Sending the status a revision already
    holds is accepted and changes nothing, so a repeated submission does not
    fail.

    `completed_at` is read from the server's clock rather than accepted from a
    caller, and is cleared by any move off `completed`. There is deliberately no
    `skipped_at`, no date, and **no reason field**: asking why a learner skipped
    a review would invite the product to form a view about the answer.

    **Only this revision moves.** No other revision, no plan, no plan item, and
    **no learning stage** — a completed review says the work happened, not that
    the topic is now understood.

    `scheduled` is not accepted: the column holds it, but nothing collects the
    date it would need.

    REV-003. Serves FR-006.
    """
    try:
        revision = reviser.record_status(revision_id, request.to_status_change())
    except RevisionNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except UnknownRevisionStatusError as error:
        raise RequestRejected(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
            details=[
                ErrorDetail(field="status", message=str(error), type="unknown_revision_status")
            ],
        ) from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return RevisionResponse(data=RevisionSchema.of(revision))
