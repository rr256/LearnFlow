"""The mentor endpoint (MNT-001).

**The first mentor capability in LearnFlow**, and the first route anywhere in it
that can cause an outbound request. It is contracted by
[ADR-039](../../../../docs/adr/ADR-039-source-grounded-study-answers.md) and
advances **FR-008 — Grounded Mentor Assistance**.

**It implements MNT-001 narrowly, and the narrowing is deliberate.** The
catalogued contract promises a mentor answer, source references, **and suggested
next actions**; this build returns the first two and **not the third**. Suggesting
what a learner should do next is a recommendation, and a recommendation drawn
from a model reading their notes is a different decision with its own privacy and
scope questions. The same narrowing shape RES-001 used for its unimplemented
upload clause.

**Retrieval decides whether a model is asked.** With no passage found, the use
case returns before any request is built, and `outcome` says which of the three
empty cases applies. The endpoint therefore cannot answer from a model's own
training: `docs/ai/prompts.md`'s rule that an answer is never claimed to be
grounded when retrieval did not succeed is enforced by control flow rather than
by a prompt.

**A provider failure is a `200`, not a `502`.** The retrieval half succeeded and
its passages are worth reading, so the response carries them with an `outcome`
naming what went wrong. Reporting a gateway error would throw away the learner's
own notes to report a fault in something they can restart, and would make the
screen unable to show what it had found.

**Nothing is stored.** No question, no answer, and no record that either
happened, so there is no history endpoint and nothing to delete.

**No note text and no question ever appears in an error.** A refusal names the
topic identifier or the rule and nothing else, per docs/api/conventions.md.

**MNT-002 stays unimplemented.** Availability is answered by asking a question:
a provider that cannot be reached says so through `outcome`, so a separate probe
would be a second way to learn the same thing.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import (
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_CONTENT,
)

from app.application.use_cases.answer_topic_question import (
    AnswerTopicQuestion,
    StudyAnswerError,
)
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.retrieve_topic_notes import (
    LearnerNotSetUpError,
    UnknownTopicError,
)
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_study_answer
from app.presentation.api.errors import ErrorResponse
from app.presentation.api.schemas.study_answer import (
    StudyAnswerResponse,
    StudyAnswerSchema,
    StudyQuestionRequest,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/mentor", tags=["mentor"])

Mentor = Annotated[AnswerTopicQuestion, Depends(provide_study_answer)]


@router.post(
    "/questions",
    summary="Ask a question about one topic, answered from your own notes",
    response_model=StudyAnswerResponse,
    responses={
        HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        HTTP_409_CONFLICT: {"model": ErrorResponse},
        HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
def ask_study_question(mentor: Mentor, body: StudyQuestionRequest) -> StudyAnswerResponse:
    """Answer a question about one topic, grounded in the learner's own notes.

    **The AI provider is asked only when passages were found.** Where the
    learner has linked no material, has no active note, or has nothing mentioning
    the topic, this returns before any prompt is built and `outcome` says which —
    because linking material, writing a note, and trying another topic are
    different next steps. **No request leaves the process on those paths.**

    **Only the question and the retrieved passages are sent**, with the topic and
    subject name for context. No identifier of any kind, no note title, no
    resource title, no whole note, and nothing about the learner's plan,
    progress, revisions, or practice. The provider selected today runs locally
    (ADR-004), so in this build nothing leaves the machine at all.

    **The citations are what was consulted.** `passages` records what LearnFlow
    retrieved and sent, captured before the provider was asked; nothing reads a
    source back out of the answer text.

    **A `POST` that writes nothing.** It is a `POST` because a question is a
    request body rather than an address — putting a learner's words in a URL puts
    them in logs and history — and not because anything is created. Asking twice
    stores nothing either time.

    Nothing else moves: no learning stage, plan, plan item, revision, or quiz.

    MNT-001, narrowed: it returns the answer and its source references, and
    deliberately **not** the suggested next actions the catalogue also lists.

    Raises:
        HTTPException: `422` when the question is blank; `404` when the topic
            names nothing stored; `409` when no learner is set up, or when more
            than one is stored.
    """
    try:
        result = mentor.answer(topic_id=body.topic_id, question=body.question)
    except StudyAnswerError as error:
        # A question of only whitespace satisfies `min_length` and is still not a
        # question, so the rule lives in the use case and is mapped back here.
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    except UnknownTopicError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (LearnerNotSetUpError, AmbiguousLocalLearnerError) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return StudyAnswerResponse(data=StudyAnswerSchema.of(result))
