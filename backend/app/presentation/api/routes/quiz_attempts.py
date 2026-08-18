"""Quiz-attempt endpoints (QZ-005, QZ-006, and QZ-007).

They serve **FR-009 — Topic Checkpoint Practice**: submitting an attempt, having
it marked, and reading back what happened.

**Marking is deterministic and immediate.** `app.domain.checkpoint_marking` marks
each answer by comparing it with the expected option; no AI provider is reached,
and the same answers always produce the same result.

**No response here carries a score.** There is no total, no mark, no count of
correct answers, and no percentage: a learner reads what became of each question,
one at a time. `quiz_attempts.score` and the marks columns are not created at
all. See docs/domain/terminology.md and ADR-033.

**An unanswered question is not a wrong one.** A question the submission omits
reads back with `is_correct: null`, never `false`.

Every route here is thin: validate, call the use case, map the result or its
error to a documented response. No route touches a session, a model, or a query
(docs/architecture/dependency-rules.md).

No route accepts a learner identifier. The effective learner is resolved
server-side (docs/api/conventions.md).
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
from app.application.use_cases.manage_checkpoint_quizzes import (
    AttemptAlreadyMarkedError,
    AttemptNotFoundError,
    DuplicateAnswerError,
    ManageCheckpointQuizzes,
    UnknownOptionError,
    UnknownQuestionError,
)
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_checkpoint_quizzes
from app.presentation.api.errors import ErrorDetail, ErrorResponse, RequestRejected
from app.presentation.api.schemas.checkpoint_practice import (
    AttemptCollectionResponse,
    AttemptResponse,
    AttemptSchema,
    SubmitAttemptRequest,
)
from app.presentation.api.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

router = APIRouter(prefix=f"{API_V1_PREFIX}/quiz-attempts", tags=["checkpoint practice"])

_NOT_FOUND_RESPONSE = {HTTP_404_NOT_FOUND: {"model": ErrorResponse}}
_CONFLICT_RESPONSE = {HTTP_409_CONFLICT: {"model": ErrorResponse}}

Practice = Annotated[ManageCheckpointQuizzes, Depends(provide_checkpoint_quizzes)]


def _rejected(field: str, message: str, rule: str) -> RequestRejected:
    """One field-level rejection, in the documented error envelope."""
    return RequestRejected(
        status_code=HTTP_422_UNPROCESSABLE_CONTENT,
        detail=message,
        details=[ErrorDetail(field=field, message=message, type=rule)],
    )


@router.post(
    "/{attempt_id}/submit",
    summary="Submit an attempt's answers and have them marked",
    response_model=AttemptResponse,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def submit_attempt(
    attempt_id: uuid.UUID, request: SubmitAttemptRequest, practice: Practice
) -> AttemptResponse:
    """Submit every answer at once, and read the marked result back.

    **The whole attempt is submitted together.** QZ-004, which saves one answer
    before submission, is deliberately not implemented: a single submission is one
    form post that works with no JavaScript, and saving answers one at a time
    needs a client this build does not have.

    A question the submission leaves out is recorded as **unanswered** — never as
    wrong. Submitting an empty list is allowed, and marks every question
    unanswered.

    **Submitting twice is refused with `409`.** A record of what happened is not
    edited after the fact, which is the position PLN-004 takes for an item on a
    superseded plan; the learner starts a new attempt instead, and both stay
    readable.

    **The result carries no score.** Each question reads back as correct, not
    correct, or unanswered, with the expected answer and the explanation the
    question was written with.

    Nothing else moves: no learning stage, no plan, no plan item, and no revision.
    A checkpoint says what happened in one attempt; it does not claim a topic is
    understood.

    QZ-005. Serves FR-009.
    """
    try:
        attempt = practice.submit(attempt_id, request.to_submissions())
    except AttemptNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AttemptAlreadyMarkedError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    except UnknownQuestionError as error:
        raise _rejected("body.answers", str(error), "unknown_question") from error
    except DuplicateAnswerError as error:
        raise _rejected("body.answers", str(error), "duplicate_answer") from error
    except UnknownOptionError as error:
        raise _rejected("body.answers", str(error), "unknown_option") from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return AttemptResponse(data=AttemptSchema.of(attempt))


@router.get(
    "",
    summary="List the learner's quiz attempts",
    response_model=AttemptCollectionResponse,
    responses=_CONFLICT_RESPONSE,
)
def list_attempts(
    practice: Practice,
    limit: Annotated[
        int, Query(ge=1, le=MAX_PAGE_SIZE, description="Maximum number of attempts to return.")
    ] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, description="Number of attempts to skip.")] = 0,
) -> AttemptCollectionResponse:
    """Read the local learner's attempts, newest first.

    **Nothing is counted, totalled, or compared.** The collection is a list of
    what happened, and no attempt is scored against another.

    An installation where setup has not run has no learner and therefore no
    attempts, which is an empty page rather than a failure.

    QZ-006. Serves FR-009.
    """
    try:
        page = practice.list_attempts(limit=limit, offset=offset)
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return AttemptCollectionResponse.of(page, limit=limit, offset=offset)


@router.get(
    "/{attempt_id}",
    summary="Read one attempt and what became of each question",
    response_model=AttemptResponse,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def read_attempt(attempt_id: uuid.UUID, practice: Practice) -> AttemptResponse:
    """Read one of the learner's attempts.

    An attempt still in progress reads back **without** its expected answers and
    explanations, so opening a result before submitting reveals nothing.

    An attempt belonging to somebody else is reported as missing rather than
    forbidden, the rule every learner-owned read here follows.

    QZ-007. Serves FR-009.
    """
    try:
        attempt = practice.read_attempt(attempt_id)
    except AttemptNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return AttemptResponse(data=AttemptSchema.of(attempt))
