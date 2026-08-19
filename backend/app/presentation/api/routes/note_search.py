"""Topic-note retrieval endpoint (RES-013).

It advances **FR-008 — Grounded Mentor Assistance** by its retrieval criterion
alone, and meets none of the others: **there is no mentor here.** Nothing on this
route asks a model anything, generates an answer, summarises, or explains. What
comes back is the learner's own words with the material they came from named
beside them.

**It is local and deterministic.** The search is PostgreSQL's own full-text
search: no embedding provider, no vector store, no AI provider, no external API,
no URL fetch, no background job. The same request returns the same passages.

**It runs only when the learner asks.** Nothing triggers a search from a page
render or a save — a learner chooses a topic and submits.

**It writes nothing**, including no record that a search happened: there is no
search history, because storing what a learner looked for is a second feature
with its own privacy question.

**No note text ever appears in an error.** A refusal names the topic identifier
or the rule and nothing else, per docs/api/conventions.md — the rule that matters
most where the data is a learner's own study material.

This is catalogued under the resource family rather than the mentor one: it
searches resource notes, and MNT-001 and MNT-002 stay unimplemented because
nothing generates an answer. See ADR-038.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.status import HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.retrieve_topic_notes import (
    LearnerNotSetUpError,
    RetrieveTopicNotes,
    UnknownTopicError,
)
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_topic_note_retrieval
from app.presentation.api.errors import ErrorResponse
from app.presentation.api.schemas.note_retrieval import (
    TopicNoteSearchResponse,
    TopicNoteSearchSchema,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/resource-notes", tags=["resource notes"])
"""
**This router must be registered before `resource_notes.router`.**

`/resource-notes/{note_id}` would otherwise capture `/resource-notes/search`:
Starlette matches a path parameter against any segment and only *then*
validates it as a UUID, so the collision would surface as a `422` about a
malformed identifier rather than as a route that never ran. The composition
root fixes the order, and an API test holds it there.
"""

Retriever = Annotated[RetrieveTopicNotes, Depends(provide_topic_note_retrieval)]


@router.get(
    "/search",
    summary="Find passages in your own notes for a topic",
    response_model=TopicNoteSearchResponse,
    responses={
        HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def search_topic_notes(
    retriever: Retriever,
    topic_id: Annotated[uuid.UUID, Query(description="The curriculum topic to find passages for.")],
) -> TopicNoteSearchResponse:
    """Return passages from the learner's own notes that mention this topic.

    **The topic is the query.** There is no free-text search field: a learner
    chooses a topic, and its name supplies the terms. A typed query would be a
    different feature with its own question about what is recorded.

    **Only the learner's own material is searched, and only where they said it
    covers this topic**: a note is considered when it is `active`, its resource is
    `registered` and owned by them, and that resource is linked to this topic.
    Archived material drops out, exactly as it does from the curriculum, revision,
    and plan screens.

    An empty answer says **why**, through `outcome`: the learner has linked no
    material here, the linked material carries no active note, or notes exist and
    none mentions the topic. Those ask for three different next steps, so they are
    not collapsed into one.

    **Passages are ordered by relevance and carry no relevance figure.** The order
    is all that relevance decides.

    Nothing is written, and nothing else moves: no note, resource, learning stage,
    plan, plan item, revision, or quiz.

    RES-013. Serves FR-008's retrieval criterion.
    """
    try:
        result = retriever.search(topic_id)
    except UnknownTopicError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (LearnerNotSetUpError, AmbiguousLocalLearnerError) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return TopicNoteSearchResponse(data=TopicNoteSearchSchema.of(result))
