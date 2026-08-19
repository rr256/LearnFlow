"""Resource-note endpoints (RES-009 to RES-012).

They extend **FR-007 — Learning Resource Organization** and lay the first
foundation for **FR-008 — Grounded Mentor Assistance**: keeping the text a
learner writes or pastes against the material they study from, so that something
exists to ground an answer in later.

**They store text and do nothing else with it.** Nothing here uploads a file,
fetches an address, downloads a page, extracts text from a document, runs OCR,
chunks, embeds, indexes, searches, ranks, or answers a question. No AI provider,
embedding provider, or vector store is reached, and the use case behind these
routes binds none — so a learner's note has no path out of this process.
`resources.storage_key`, `resources.metadata`, and `resource_ingestions` all
remain absent, and RES-005 to RES-008 remain unimplemented.

Every route here is thin: validate, call the use case, map the result or its
error to a documented response. No route touches a session, a model, or a query
(docs/architecture/dependency-rules.md).

No route accepts a learner identifier. A note is reached through its resource,
and the effective learner is resolved server-side, so a request cannot read or
change another learner's notes (docs/api/conventions.md).

**No refusal echoes the learner's text.** A rejected note is reported by field
and rule; the value never appears in a message, a detail, or a log line.

**Nothing is deleted.** A note the learner is finished with is put aside with
`status: archived` through RES-012, which is reversible — the position ADR-032
takes for a resource.
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

from app.application.dto.resource_note import RESOURCE_NOTE_STATUSES, ResourceNoteFilters
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_resource_notes import (
    ArchivedResourceError,
    EmptyNoteUpdateError,
    ManageResourceNotes,
    MissingNoteBodyError,
    MissingNoteTitleError,
    NoteTitleTooLongError,
    NoteTooLongError,
    ResourceNoteNotFoundError,
    ResourceNotFoundError,
    TooManyNotesError,
    UnknownNoteStatusError,
)
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_resource_notes
from app.presentation.api.errors import ErrorDetail, ErrorResponse, RequestRejected
from app.presentation.api.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.presentation.api.schemas.resource_note import (
    ResourceNoteCollectionResponse,
    ResourceNoteResponse,
    ResourceNoteSchema,
    UpdateResourceNoteRequest,
    WriteResourceNoteRequest,
)

router = APIRouter(prefix=API_V1_PREFIX, tags=["resource notes"])

_NOT_FOUND_RESPONSE = {HTTP_404_NOT_FOUND: {"model": ErrorResponse}}
_CONFLICT_RESPONSE = {HTTP_409_CONFLICT: {"model": ErrorResponse}}

Keeper = Annotated[ManageResourceNotes, Depends(provide_resource_notes)]


def _rejected(field: str, message: str, rule: str) -> RequestRejected:
    """One field-level rejection, in the documented error envelope.

    The rejected value is never echoed back, per docs/api/conventions.md. That
    holds hardest here: the value is the learner's own study material.
    """
    return RequestRejected(
        status_code=HTTP_422_UNPROCESSABLE_CONTENT,
        detail=message,
        details=[ErrorDetail(field=field, message=message, type=rule)],
    )


@router.post(
    "/resources/{resource_id}/notes",
    summary="Keep a note against a piece of study material",
    response_model=ResourceNoteResponse,
    status_code=HTTP_201_CREATED,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def write_resource_note(
    resource_id: uuid.UUID, request: WriteResourceNoteRequest, keeper: Keeper
) -> ResourceNoteResponse:
    """Store one note the learner wrote or pasted.

    **The text is stored and nothing else is done with it.** It is not sent to
    any provider, indexed, searched, summarised, or read by anything. It is kept
    exactly as written, minus surrounding whitespace, so a learner's line breaks
    and spacing survive.

    Material the learner has put aside is read-only, so writing a note against an
    archived resource is a `409`: they put it back through RES-004 first.

    Nothing else moves: no resource, no topic link, no learning stage, no plan,
    no plan item, no revision, and no quiz.

    RES-009. Serves FR-007 and lays the first foundation for FR-008.
    """
    try:
        note = keeper.add(resource_id, request.to_new_note())
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ArchivedResourceError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    except MissingNoteTitleError as error:
        raise _rejected("body.title", str(error), "missing_title") from error
    except NoteTitleTooLongError as error:
        raise _rejected("body.title", str(error), "title_too_long") from error
    except MissingNoteBodyError as error:
        raise _rejected("body.body", str(error), "missing_note_body") from error
    except NoteTooLongError as error:
        raise _rejected("body.body", str(error), "note_too_long") from error
    except TooManyNotesError as error:
        raise _rejected("body", str(error), "too_many_notes") from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return ResourceNoteResponse(data=ResourceNoteSchema.of(note))


@router.get(
    "/resources/{resource_id}/notes",
    summary="List the notes kept against one piece of study material",
    response_model=ResourceNoteCollectionResponse,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def list_resource_notes(
    resource_id: uuid.UUID,
    keeper: Keeper,
    status: Annotated[
        str | None, Query(description=f"One of: {', '.join(RESOURCE_NOTE_STATUSES)}.")
    ] = None,
    limit: Annotated[
        int, Query(ge=1, le=MAX_PAGE_SIZE, description="Maximum number of notes to return.")
    ] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, description="Number of notes to skip.")] = 0,
) -> ResourceNoteCollectionResponse:
    """Read one resource's notes, newest first.

    **No status is assumed.** A caller wanting only what the learner is using
    asks for `active`, and one wanting what has been put aside asks for
    `archived`, which is how RES-002, PLN-002, and REV-001 treat their own.

    The notes of an **archived** resource are readable. Putting material aside
    stops it being written to and takes it off the screens that show a topic's
    material; it destroys nothing and hides nothing a learner goes looking for.

    Nothing is ranked, scored, or counted here beyond the pagination block every
    collection carries.

    RES-010. Serves FR-007.
    """
    try:
        page = keeper.list_notes(
            resource_id,
            filters=ResourceNoteFilters(status=status),
            limit=limit,
            offset=offset,
        )
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except UnknownNoteStatusError as error:
        raise _rejected("query.status", str(error), "unknown_note_status") from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return ResourceNoteCollectionResponse.of(page, limit=limit, offset=offset)


@router.get(
    "/resource-notes/{note_id}",
    summary="Read one note",
    response_model=ResourceNoteResponse,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def read_resource_note(note_id: uuid.UUID, keeper: Keeper) -> ResourceNoteResponse:
    """Read one of the learner's notes, exactly as they wrote it.

    A note whose material belongs to somebody else is reported as missing rather
    than forbidden, the rule every learner-owned read here follows: saying "that
    exists but is not yours" would confirm a record the caller may not read.

    RES-011. Serves FR-007.
    """
    try:
        note = keeper.read(note_id)
    except ResourceNoteNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return ResourceNoteResponse(data=ResourceNoteSchema.of(note))


@router.patch(
    "/resource-notes/{note_id}",
    summary="Correct a note, or put it aside",
    response_model=ResourceNoteResponse,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def update_resource_note(
    note_id: uuid.UUID, request: UpdateResourceNoteRequest, keeper: Keeper
) -> ResourceNoteResponse:
    """Correct what a note says, or put it aside.

    A field the request omits is left alone; no field may be null, because a note
    always has a title, a body, and a status.

    **A note is corrected in place, as often as the learner likes.** Nothing
    reads a note, so no stored record can be made to disagree with a correction —
    the condition ADR-035 could not meet for a question a quiz had already asked,
    and the reason this endpoint does not fix a note's wording after the fact.

    **Putting a note aside is reversible and destroys nothing.** There is no
    delete.

    Material the learner has put aside is read-only, so changing a note on an
    archived resource is a `409`: they put the material back first.

    **Only the named note moves.** No other note, no resource, no topic link, no
    learning stage, no plan, no plan item, no revision, and no quiz.

    RES-012. Serves FR-007.
    """
    try:
        note = keeper.update(note_id, request.to_changes())
    except ResourceNoteNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ArchivedResourceError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    except EmptyNoteUpdateError as error:
        raise _rejected("body", str(error), "empty_update") from error
    except MissingNoteTitleError as error:
        raise _rejected("body.title", str(error), "missing_title") from error
    except NoteTitleTooLongError as error:
        raise _rejected("body.title", str(error), "title_too_long") from error
    except MissingNoteBodyError as error:
        raise _rejected("body.body", str(error), "missing_note_body") from error
    except NoteTooLongError as error:
        raise _rejected("body.body", str(error), "note_too_long") from error
    except UnknownNoteStatusError as error:
        raise _rejected("body.status", str(error), "unknown_note_status") from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return ResourceNoteResponse(data=ResourceNoteSchema.of(note))
