"""Checkpoint-quiz endpoints (QZ-001, QZ-002, and QZ-003).

They serve **FR-009 — Topic Checkpoint Practice**: assembling a topic-focused
quiz from the questions the learner has written, reading it back safely, and
beginning an attempt at it.

**Deterministic, with no AI provider.** A quiz is assembled by the pure rules in
`app.domain.checkpoint_marking`: every ready question the learner wrote for the
chosen topics, in the order they wrote them. Nothing is generated, sampled, or
randomised, and nothing is selected in preference to anything else — choosing
which few to ask would be a ranking. See ADR-033.

Every route here is thin: validate, call the use case, map the result or its
error to a documented response. No route touches a session, a model, or a query
(docs/architecture/dependency-rules.md).

No route accepts a learner identifier. The effective learner is resolved
server-side (docs/api/conventions.md).

**QZ-004 is deliberately not implemented.** Saving one answer before submission
needs a client that keeps an attempt open across requests; a learner submits the
whole attempt at once through QZ-005 instead, which is one form post that works
with no JavaScript.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_CONTENT,
)

from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_checkpoint_quizzes import (
    DuplicateQuizTopicError,
    LearnerNotSetUpError,
    ManageCheckpointQuizzes,
    MissingQuizTopicError,
    NoQuestionsForTopicsError,
    QuizNotFoundError,
    TooManyQuizTopicsError,
    UnknownTopicError,
)
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_checkpoint_quizzes
from app.presentation.api.errors import ErrorDetail, ErrorResponse, RequestRejected
from app.presentation.api.schemas.checkpoint_practice import (
    AssembleQuizRequest,
    AttemptResponse,
    AttemptSchema,
    QuizResponse,
    QuizSchema,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/checkpoint-quizzes", tags=["checkpoint practice"])

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
    "/generate",
    summary="Assemble a checkpoint quiz from your questions for these topics",
    response_model=QuizResponse,
    status_code=HTTP_201_CREATED,
    responses=_CONFLICT_RESPONSE,
)
def assemble_quiz(request: AssembleQuizRequest, practice: Practice) -> QuizResponse:
    """Assemble a quiz covering the topics the learner chose.

    **Every ready question you wrote for those topics is asked**, in the order you
    wrote them. LearnFlow selects none and leaves none out, so a quiz's length is
    the learner's own decision rather than a number this endpoint picked.

    A **retired** question is left out, which is what retiring one means. A
    question covering two of the chosen topics is asked once.

    A request naming no topic is refused, which is ADR-008's rule; so is one for
    topics the learner has written no questions for, because a quiz that asks
    nothing cannot be attempted.

    Asking again assembles a **new** quiz rather than returning the last one:
    nothing is superseded, and nothing is deleted.

    Despite the path, **nothing is generated**: `generate` is the catalogued verb
    for a deterministic assembly, exactly as it is for PLN-001.

    Nothing else moves: no learning stage, no plan, no plan item, and no revision.

    QZ-001. Serves FR-009.
    """
    try:
        quiz = practice.assemble(request.to_new_quiz())
    except MissingQuizTopicError as error:
        raise _rejected("body.topic_ids", str(error), "missing_topic") from error
    except UnknownTopicError as error:
        raise _rejected("body.topic_ids", str(error), "unknown_topic") from error
    except DuplicateQuizTopicError as error:
        raise _rejected("body.topic_ids", str(error), "duplicate_topic") from error
    except TooManyQuizTopicsError as error:
        raise _rejected("body.topic_ids", str(error), "too_many_topics") from error
    except NoQuestionsForTopicsError as error:
        raise _rejected("body.topic_ids", str(error), "no_questions_for_topics") from error
    except (LearnerNotSetUpError, AmbiguousLocalLearnerError) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return QuizResponse(data=QuizSchema.of(quiz))


@router.get(
    "/{quiz_id}",
    summary="Read a quiz's questions, without their answers",
    response_model=QuizResponse,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def read_quiz(quiz_id: uuid.UUID, practice: Practice) -> QuizResponse:
    """Read one of the learner's quizzes, as it is to be taken.

    **No expected answer and no explanation is returned.** The response shape has
    nowhere to put either, so this cannot leak one by forgetting to strip a field.
    The answers appear once an attempt has been submitted, through QZ-007.

    A quiz belonging to somebody else is reported as missing rather than
    forbidden, the rule every learner-owned read here follows.

    QZ-002. Serves FR-009.
    """
    try:
        quiz = practice.read_quiz(quiz_id)
    except QuizNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return QuizResponse(data=QuizSchema.of(quiz))


@router.post(
    "/{quiz_id}/attempts",
    summary="Begin an attempt at a checkpoint quiz",
    response_model=AttemptResponse,
    status_code=HTTP_201_CREATED,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def start_attempt(quiz_id: uuid.UUID, practice: Practice, response: Response) -> AttemptResponse:
    """Begin an attempt, or return the one already open.

    **Asking twice starts nothing the second time.** An unfinished attempt at the
    same quiz is returned with `200 OK` rather than a second attempt being
    created, which is the position REV-004 takes for a review already waiting: a
    learner who reloads or double-submits should not accumulate records they never
    asked for. A newly created attempt is `201 Created`.

    Nothing else moves: no learning stage, no plan, no plan item, and no revision.

    QZ-003. Serves FR-009.
    """
    try:
        attempt, created = practice.start_attempt(quiz_id)
    except QuizNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (LearnerNotSetUpError, AmbiguousLocalLearnerError) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    if not created:
        response.status_code = HTTP_200_OK
    return AttemptResponse(data=AttemptSchema.of(attempt))
