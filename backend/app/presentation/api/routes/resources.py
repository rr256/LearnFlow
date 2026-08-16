"""Learning-resource endpoints (RES-001 to RES-004).

They serve **FR-007 — Learning Resource Organization**: recording where a
learner's study material is, saying which curriculum topics it covers, finding a
topic's material again, and keeping the record current.

Every route here is thin: validate, call the use case, map the result or its
error to a documented response. No route touches a session, a model, or a query
(docs/architecture/dependency-rules.md).

No route accepts a learner identifier. The effective learner is resolved
server-side, so a request cannot read or change another learner's material
(docs/api/conventions.md).

**These endpoints expose safe metadata only.** `external_reference` holds an
`http` or `https` address and nothing else, so no absolute local filesystem path
is stored or returned, and no provider credential exists to leak. Material that
is not on the web is described by `source_label`, in the learner's own words.

**RES-005 to RES-008 are not implemented.** RES-006 to RES-008 need
`resource_ingestions` and an extractor, neither of which exists. RES-005 would
delete; a learner puts material aside with `status: archived` through RES-004
instead, which is reversible and destroys nothing. See ADR-032.
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

from app.application.dto.resource import RESOURCE_STATUSES, RESOURCE_TYPES, ResourceFilters
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_resources import (
    DuplicateTopicLinkError,
    EmptyResourceUpdateError,
    LearnerNotSetUpError,
    ManageResources,
    MissingResourceLocationError,
    MissingResourceTitleError,
    ResourceNotFoundError,
    TooManyTopicLinksError,
    UnknownResourceStatusError,
    UnknownResourceTypeError,
    UnknownTopicError,
    UnsupportedReferenceSchemeError,
)
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_resources
from app.presentation.api.errors import ErrorDetail, ErrorResponse, RequestRejected
from app.presentation.api.schemas.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.presentation.api.schemas.resource import (
    RegisterResourceRequest,
    ResourceCollectionResponse,
    ResourceResponse,
    ResourceSchema,
    UpdateResourceRequest,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/resources", tags=["resources"])

_NOT_FOUND_RESPONSE = {HTTP_404_NOT_FOUND: {"model": ErrorResponse}}
_CONFLICT_RESPONSE = {HTTP_409_CONFLICT: {"model": ErrorResponse}}

Cataloguer = Annotated[ManageResources, Depends(provide_resources)]


def _rejected(field: str, message: str, rule: str) -> RequestRejected:
    """One field-level rejection, in the documented error envelope.

    The rejected value is never echoed back, per docs/api/conventions.md.
    """
    return RequestRejected(
        status_code=HTTP_422_UNPROCESSABLE_CONTENT,
        detail=message,
        details=[ErrorDetail(field=field, message=message, type=rule)],
    )


@router.post(
    "",
    summary="Register where a piece of study material is, and what it covers",
    response_model=ResourceResponse,
    status_code=HTTP_201_CREATED,
    responses=_CONFLICT_RESPONSE,
)
def register_resource(request: RegisterResourceRequest, cataloguer: Cataloguer) -> ResourceResponse:
    """Record one piece of the learner's study material.

    **A resource is a record of where material is, never the material.** Nothing
    is uploaded, downloaded, extracted, or indexed: `external_reference` is a web
    address and `source_label` is where the material is in the learner's own
    words, which is what carries a book, a folder, or a lecture series that is
    not on the web.

    A resource may name **any** stored topic, including one that only groups
    subtopics — deliberately unlike PRG-004, which refuses a stage on a grouping
    topic, because a textbook may genuinely cover a whole heading while a claim
    about understanding one cannot.

    Nothing else moves: no learning stage, no plan, no plan item, and no
    revision.

    RES-001. Serves FR-007.
    """
    try:
        resource = cataloguer.register(request.to_new_resource())
    except UnknownResourceTypeError as error:
        raise _rejected("body.resource_type", str(error), "unknown_resource_type") from error
    except MissingResourceTitleError as error:
        raise _rejected("body.title", str(error), "missing_title") from error
    except MissingResourceLocationError as error:
        raise _rejected("body.source_label", str(error), "missing_location") from error
    except UnsupportedReferenceSchemeError as error:
        raise _rejected(
            "body.external_reference", str(error), "unsupported_reference_scheme"
        ) from error
    except UnknownTopicError as error:
        raise _rejected("body.topic_ids", str(error), "unknown_topic") from error
    except DuplicateTopicLinkError as error:
        raise _rejected("body.topic_ids", str(error), "duplicate_topic") from error
    except TooManyTopicLinksError as error:
        raise _rejected("body.topic_ids", str(error), "too_many_topics") from error
    except (LearnerNotSetUpError, AmbiguousLocalLearnerError) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return ResourceResponse(data=ResourceSchema.of(resource))


@router.get(
    "",
    summary="List the learner's study material",
    response_model=ResourceCollectionResponse,
    responses=_CONFLICT_RESPONSE,
)
def list_resources(
    cataloguer: Cataloguer,
    topic_id: Annotated[
        uuid.UUID | None, Query(description="Only material linked to this topic.")
    ] = None,
    resource_type: Annotated[
        str | None, Query(description=f"One of: {', '.join(RESOURCE_TYPES)}.")
    ] = None,
    status: Annotated[
        str | None, Query(description=f"One of: {', '.join(RESOURCE_STATUSES)}.")
    ] = None,
    limit: Annotated[
        int, Query(ge=1, le=MAX_PAGE_SIZE, description="Maximum number of resources to return.")
    ] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, description="Number of resources to skip.")] = 0,
) -> ResourceCollectionResponse:
    """Read the local learner's study material, newest first.

    `topic_id` is what answers FR-007's fourth acceptance criterion — finding the
    material associated with a topic — without a client holding the whole
    collection to filter it.

    **No status is assumed.** A caller wanting only what is in the catalogue asks
    for `registered`, and one wanting what has been put aside asks for
    `archived`, which is how PLN-002 and REV-001 treat their own statuses.

    An installation where setup has not run has no learner and therefore no
    resources, which is an empty page rather than a failure. A `topic_id`
    matching nothing is an empty page too; an unknown *type* or *status* is a
    `422`, because a caller asking for one has misread the contract.

    RES-002. Serves FR-007.
    """
    try:
        page = cataloguer.list_resources(
            filters=ResourceFilters(topic_id=topic_id, resource_type=resource_type, status=status),
            limit=limit,
            offset=offset,
        )
    except UnknownResourceTypeError as error:
        raise _rejected("query.resource_type", str(error), "unknown_resource_type") from error
    except UnknownResourceStatusError as error:
        raise _rejected("query.status", str(error), "unknown_resource_status") from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return ResourceCollectionResponse.of(page, limit=limit, offset=offset)


@router.get(
    "/{resource_id}",
    summary="Read one resource and the topics it covers",
    response_model=ResourceResponse,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def read_resource(resource_id: uuid.UUID, cataloguer: Cataloguer) -> ResourceResponse:
    """Read one of the learner's resources.

    Material owned by somebody else is reported as missing rather than forbidden,
    the rule every learner-owned read here follows: saying "that exists but is
    not yours" would confirm a record the caller may not read.

    RES-003. Serves FR-007.
    """
    try:
        resource = cataloguer.read(resource_id)
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return ResourceResponse(data=ResourceSchema.of(resource))


@router.patch(
    "/{resource_id}",
    summary="Change a resource's details, its topics, or whether it is put aside",
    response_model=ResourceResponse,
    responses=_NOT_FOUND_RESPONSE | _CONFLICT_RESPONSE,
)
def update_resource(
    resource_id: uuid.UUID, request: UpdateResourceRequest, cataloguer: Cataloguer
) -> ResourceResponse:
    """Correct what a resource says, or put it aside.

    A field the request omits is left alone; an explicit null clears what was
    stored. A supplied `topic_ids` **replaces** the link set, so a topic left out
    of one is unlinked — GOAL-005's whole-week replacement, applied to a link
    set.

    **Archiving is reversible and destroys nothing.** `archived` puts material
    aside and `registered` brings it back; no endpoint here deletes a resource,
    which is why RES-005 stays unimplemented.

    **Only the named resource moves.** No other resource, no learning stage, no
    plan, no plan item, and no revision.

    RES-004. Serves FR-007.
    """
    try:
        resource = cataloguer.update(resource_id, request.to_changes())
    except ResourceNotFoundError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except EmptyResourceUpdateError as error:
        raise _rejected("body", str(error), "empty_update") from error
    except UnknownResourceTypeError as error:
        raise _rejected("body.resource_type", str(error), "unknown_resource_type") from error
    except UnknownResourceStatusError as error:
        raise _rejected("body.status", str(error), "unknown_resource_status") from error
    except MissingResourceTitleError as error:
        raise _rejected("body.title", str(error), "missing_title") from error
    except MissingResourceLocationError as error:
        raise _rejected("body.source_label", str(error), "missing_location") from error
    except UnsupportedReferenceSchemeError as error:
        raise _rejected(
            "body.external_reference", str(error), "unsupported_reference_scheme"
        ) from error
    except UnknownTopicError as error:
        raise _rejected("body.topic_ids", str(error), "unknown_topic") from error
    except DuplicateTopicLinkError as error:
        raise _rejected("body.topic_ids", str(error), "duplicate_topic") from error
    except TooManyTopicLinksError as error:
        raise _rejected("body.topic_ids", str(error), "too_many_topics") from error
    except AmbiguousLocalLearnerError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return ResourceResponse(data=ResourceSchema.of(resource))
