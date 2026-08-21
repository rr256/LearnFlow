"""Stored-file endpoints for a learning resource (RES-014 to RES-017).

Contracted by
[ADR-040](../../../../docs/adr/ADR-040-learner-uploaded-resource-files.md). These
are the first endpoints in LearnFlow that accept or return a **file**.

**Upload and store, and nothing else.** Nothing here extracts text, runs OCR,
chunks, embeds, indexes, summarises, or searches; no AI provider is reached, no
URL is fetched, and no background job is started. `resource_ingestions` remains
absent, and RES-006 to RES-008 remain unimplemented.

**No filesystem path is accepted or returned.** A learner chooses a file in a
browser and its bytes arrive; LearnFlow never learns where it sat on their
machine. `storage_key` is internal and appears in no response schema, so
docs/api/endpoints.md's rule that a resource endpoint never returns an absolute
local path holds by construction.

**Nothing is deleted.** RES-005 stays unimplemented: a learner sets a file aside
with `status: archived`, reversibly, and the bytes stay in the volume. Permanent
deletion must coordinate rows and bytes together, and is a separate feature.

**A download is served as an attachment.** `Content-Disposition: attachment` and
`X-Content-Type-Options: nosniff` mean the browser saves the PDF rather than
rendering it in LearnFlow's own origin — a PDF is an active-content format, and
not rendering it in-origin is the mitigation this build offers. **No virus
scanning is performed**, which ADR-040 states plainly rather than implying
otherwise.

**No refusal echoes a filename or any byte of a file**, per
docs/api/conventions.md — the rule that matters most where the data is a
learner's own study material.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_413_CONTENT_TOO_LARGE,
    HTTP_422_UNPROCESSABLE_CONTENT,
)

from app.application.dto.resource_file import (
    MAX_FILE_BYTES,
    MAX_FILES_PER_RESOURCE,
    MAX_PAGE_COUNT,
    RESOURCE_FILE_STATUSES,
    ResourceFileRejection,
)
from app.application.use_cases.local_learner import AmbiguousLocalLearnerError
from app.application.use_cases.manage_resource_files import (
    InvalidFileStatusError,
    LearnerNotSetUpError,
    ManageResourceFiles,
    ResourceNotWritableError,
    TooManyFilesError,
    UnknownResourceError,
    UnknownResourceFileError,
    UnsupportedFileError,
)
from app.presentation.api import API_V1_PREFIX
from app.presentation.api.dependencies import provide_resource_files
from app.presentation.api.errors import ErrorResponse
from app.presentation.api.schemas.resource_file import (
    ResourceFileCollectionResponse,
    ResourceFileResponse,
    ResourceFileSchema,
    UpdateResourceFileRequest,
)

router = APIRouter(prefix=API_V1_PREFIX, tags=["resource files"])

Files = Annotated[ManageResourceFiles, Depends(provide_resource_files)]

_TOO_LARGE = {ResourceFileRejection.TOO_LARGE, ResourceFileRejection.TOO_MANY_PAGES}
"""Rejections that mean "this file exceeds a limit" rather than "this file is wrong".

Reported as `413` so a caller can tell a size problem from a format problem
without reading prose.
"""


_CHUNK_BYTES = 1024 * 1024
"""How much of an upload is read at a time.

One megabyte. The point is not throughput but the check below: reading in chunks
is what lets an oversized upload be refused **without ever holding all of it**,
which is the difference between a limit and a guideline.
"""


async def _read_bounded(upload: UploadFile) -> bytes:
    """The upload's bytes, refusing anything past `MAX_FILE_BYTES`.

    **Stops reading as soon as the limit is passed.** A caller cannot make the
    process hold an arbitrary amount of memory by claiming a small file and
    sending a large one, because the check happens between chunks rather than
    after the whole body has been materialised.

    The refusal names the limit and never the file: no byte of the upload and no
    part of its name reaches the message.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(_CHUNK_BYTES):
        total += len(chunk)
        if total > MAX_FILE_BYTES:
            raise UnsupportedFileError(
                ResourceFileRejection.TOO_LARGE,
                f"A file may be at most {MAX_FILE_BYTES // (1024 * 1024)} MB.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/resources/{resource_id}/files",
    summary="Store a PDF against this resource",
    status_code=HTTP_201_CREATED,
    response_model=ResourceFileResponse,
    responses={
        HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        HTTP_409_CONFLICT: {"model": ErrorResponse},
        HTTP_413_CONTENT_TOO_LARGE: {"model": ErrorResponse},
        HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def store_resource_file(
    files: Files,
    resource_id: uuid.UUID,
    file: Annotated[UploadFile, File(description="One PDF, at most 25 MB and 1500 pages.")],
) -> ResourceFileResponse:
    """Keep one PDF against a resource the learner owns (RES-014).

    A `multipart/form-data` request with one part, `file`.

    **Only PDFs are stored.** The file must end `.pdf`, begin with the `%PDF-`
    signature, parse as a PDF, and not be password-protected — LearnFlow refuses
    an encrypted document rather than storing something it can never open. It
    must be at most 25 MB and 1500 pages, and a resource may hold at most 20
    files.

    **A refused upload writes nothing**: no row, and no bytes. Validation happens
    before anything is stored, so a rejection cannot half-succeed.

    **The filename is metadata, never a path.** What lands on disk is named from
    a server-generated identifier, so nothing a browser sends decides where a
    file is written.

    Archived material is read-only, so uploading to it is refused with `409` —
    the rule RES-004 and RES-012 already apply.

    Nothing is extracted, indexed, or sent anywhere.

    Raises:
        HTTPException: `413` when a limit is exceeded; `422` when the file is not
            a usable PDF; `404` when the resource is not the learner's; `409`
            when it is archived, the file ceiling is reached, or no learner is
            set up.
    """
    try:
        content = await _read_bounded(file)
        record = files.store_file(
            resource_id=resource_id,
            filename=file.filename or "",
            content=content,
        )
    except UnsupportedFileError as error:
        status = (
            HTTP_413_CONTENT_TOO_LARGE
            if error.rejection in _TOO_LARGE
            else HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=status, detail=str(error)) from error
    except UnknownResourceError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (ResourceNotWritableError, TooManyFilesError) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    except (LearnerNotSetUpError, AmbiguousLocalLearnerError) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return ResourceFileResponse(data=ResourceFileSchema.of(record))


@router.get(
    "/resources/{resource_id}/files",
    summary="List the PDFs stored against this resource",
    response_model=ResourceFileCollectionResponse,
    responses={
        HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        HTTP_409_CONFLICT: {"model": ErrorResponse},
        HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
def list_resource_files(
    files: Files,
    resource_id: uuid.UUID,
    status: Annotated[
        list[str] | None,
        Query(description=f"Restrict to these statuses: {', '.join(RESOURCE_FILE_STATUSES)}."),
    ] = None,
) -> ResourceFileCollectionResponse:
    """This resource's stored files, newest first (RES-015).

    Readable whatever the resource's own status: archived material stays
    **readable** and only stops being writable.

    There is deliberately no pagination — a resource holds at most 20 files, so
    the collection is bounded by a rule and every file is always reachable.

    Raises:
        HTTPException: `404` when the resource is not the learner's; `409` when
            no learner is set up; `422` for an unknown status.
    """
    try:
        stored = files.list_files(resource_id=resource_id, statuses=tuple(status or ()))
    except InvalidFileStatusError as error:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    except UnknownResourceError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (LearnerNotSetUpError, AmbiguousLocalLearnerError) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return ResourceFileCollectionResponse(data=[ResourceFileSchema.of(record) for record in stored])


@router.get(
    "/resource-files/{file_id}/content",
    summary="Download one stored PDF",
    response_class=Response,
    responses={
        HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def download_resource_file(files: Files, file_id: uuid.UUID) -> Response:
    """The stored bytes, for the learner who owns them (RES-016).

    **Served as an attachment, never inline.** A PDF is an active-content format,
    and `Content-Disposition: attachment` with `X-Content-Type-Options: nosniff`
    means the browser saves it rather than rendering it inside LearnFlow's origin.
    That is this build's mitigation; **no virus scanning is performed**.

    **An archived file is still downloadable.** Setting material aside hides it
    from the catalogue; it does not withhold a learner's own file from them.

    A file whose bytes are missing from storage — a volume restored from a backup
    older than the database would look exactly like that — is reported as `404`
    rather than as a server fault, and the storage location is never named.

    Raises:
        HTTPException: `404` when the file is not the learner's or its bytes are
            absent; `409` when no learner is set up.
    """
    try:
        stored = files.read_file(file_id)
    except UnknownResourceFileError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (LearnerNotSetUpError, AmbiguousLocalLearnerError) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error

    return Response(
        content=stored.content,
        media_type=stored.record.content_type,
        headers={
            # RFC 6266 `filename*`, so a name with non-ASCII characters survives.
            # The value is percent-encoded, and the use case has already removed
            # quotes and control characters that could split this header.
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{_encoded(stored.record.original_filename)}"
            ),
            "X-Content-Type-Options": "nosniff",
            # A learner's own file is not a public asset.
            "Cache-Control": "private, no-store",
        },
    )


@router.patch(
    "/resource-files/{file_id}",
    summary="Set a stored PDF aside, or bring it back",
    response_model=ResourceFileResponse,
    responses={
        HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        HTTP_409_CONFLICT: {"model": ErrorResponse},
        HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
def update_resource_file(
    files: Files, file_id: uuid.UUID, body: UpdateResourceFileRequest
) -> ResourceFileResponse:
    """Move a stored file between `active` and `archived` (RES-017).

    Reversible in both directions, and **nothing is removed** either way: the
    bytes stay in the volume whichever status the row holds.

    Refused with `409` when the file's resource is archived, because archived
    material is read-only — the rule RES-012 already applies to notes.

    Raises:
        HTTPException: `422` for an unknown status; `404` when the file is not
            the learner's; `409` when its resource is archived or no learner is
            set up.
    """
    try:
        record = files.set_file_status(file_id=file_id, status=body.status)
    except InvalidFileStatusError as error:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    except UnknownResourceFileError as error:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ResourceNotWritableError as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    except (LearnerNotSetUpError, AmbiguousLocalLearnerError) as error:
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=str(error)) from error
    return ResourceFileResponse(data=ResourceFileSchema.of(record))


def _encoded(filename: str) -> str:
    """The filename, percent-encoded for an RFC 6266 `filename*` parameter."""
    from urllib.parse import quote

    return quote(filename, safe="")


__all__ = ["MAX_FILE_BYTES", "MAX_FILES_PER_RESOURCE", "MAX_PAGE_COUNT", "router"]
