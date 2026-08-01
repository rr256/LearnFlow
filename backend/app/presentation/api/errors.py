"""The error envelope every API failure is reported in.

docs/api/conventions.md fixes the shape:

    {"error": {"code": ..., "message": ..., "details": [], "request_id": ...}}

FastAPI's own failure responses do not use it -- a validation failure returns a
bare ``detail`` list, and an unhandled exception returns plain text -- so the
handlers below replace them. They are registered on the whole application rather
than on the versioned router: an unknown path never reaches a router, and a
learner-facing 404 must still arrive in the documented shape.

``request_id`` is documented as included *when available*. No correlation
identifier is generated anywhere in the backend yet, so the field is omitted
rather than sent empty; a null would tell a client a value exists.
"""

import logging
from http import HTTPStatus
from typing import Final

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import (
    HTTP_404_NOT_FOUND,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_422_UNPROCESSABLE_CONTENT,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

_logger = logging.getLogger(__name__)

# `not_found` rather than `resource_not_found`: `resource` is a canonical
# LearnFlow term for a learner's study material, and `/api/v1/resources` is
# reserved for it. A generic code carrying that word would name two concepts.
# See ADR-014 and docs/domain/terminology.md.
NOT_FOUND: Final = "not_found"
METHOD_NOT_ALLOWED: Final = "method_not_allowed"
VALIDATION_ERROR: Final = "validation_error"
INTERNAL_ERROR: Final = "internal_error"
REQUEST_FAILED: Final = "request_failed"

# The stable, machine-readable code for each status the API can currently
# return. A status with no entry falls back to REQUEST_FAILED; give it its own
# code here when an endpoint starts returning it deliberately.
ERROR_CODES_BY_STATUS: Final[dict[int, str]] = {
    HTTP_404_NOT_FOUND: NOT_FOUND,
    HTTP_405_METHOD_NOT_ALLOWED: METHOD_NOT_ALLOWED,
    HTTP_422_UNPROCESSABLE_CONTENT: VALIDATION_ERROR,
    HTTP_500_INTERNAL_SERVER_ERROR: INTERNAL_ERROR,
}

_DEFAULT_MESSAGES: Final[dict[int, str]] = {
    HTTP_404_NOT_FOUND: "The requested resource was not found.",
    HTTP_405_METHOD_NOT_ALLOWED: "That method is not supported for this path.",
    HTTP_422_UNPROCESSABLE_CONTENT: "The request failed validation.",
    HTTP_500_INTERNAL_SERVER_ERROR: "An unexpected error occurred.",
}

_FALLBACK_MESSAGE: Final = "The request could not be completed."

# Deliberately fixed text. An unhandled exception's message can carry a database
# error, a file path, or a connection string, none of which may cross the API
# boundary; the detail goes to the log instead.
_UNEXPECTED_ERROR_MESSAGE: Final = "An unexpected error occurred."


class ErrorDetail(BaseModel):
    """One field-level reason a request was rejected."""

    field: str = Field(description="Dotted path to the offending part of the request.")
    message: str = Field(description="What is wrong with it.")
    type: str = Field(description="Stable machine-readable validation rule name.")


class ApiError(BaseModel):
    """The body of an error response."""

    code: str = Field(description="Stable, machine-readable error code.")
    message: str = Field(description="Safe explanation for a learner or developer.")
    details: list[ErrorDetail] = Field(
        default_factory=list,
        description="Field-level validation information; empty when none applies.",
    )


class ErrorResponse(BaseModel):
    """The documented error envelope."""

    error: ApiError


def register_error_handlers(app: FastAPI) -> None:
    """Replace FastAPI's default error bodies with the documented envelope."""
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected_error)


def _handle_validation_error(request: Request, exception: RequestValidationError) -> JSONResponse:
    """Report a rejected request field by field.

    Only the location, the rule, and its message are returned. Pydantic also
    reports the offending input, which is echoed back to a client that may have
    sent something it should not see repeated.
    """
    details = [
        ErrorDetail(
            field=".".join(str(part) for part in error.get("loc", ())),
            message=str(error.get("msg", "")),
            type=str(error.get("type", "")),
        )
        for error in exception.errors()
    ]
    return _envelope(
        status_code=HTTP_422_UNPROCESSABLE_CONTENT,
        message=_DEFAULT_MESSAGES[HTTP_422_UNPROCESSABLE_CONTENT],
        details=details,
    )


def _handle_http_exception(request: Request, exception: StarletteHTTPException) -> JSONResponse:
    """Report a raised HTTP failure, keeping the message the route chose.

    Starlette fills `detail` with the bare reason phrase -- `Not Found` -- when
    nothing chose a message, which is a status name rather than something a
    learner can act on. That case falls back to the fuller wording below.
    """
    default = _DEFAULT_MESSAGES.get(exception.status_code, _FALLBACK_MESSAGE)
    detail = exception.detail if isinstance(exception.detail, str) else ""
    message = detail if detail and detail != _reason_phrase(exception.status_code) else default
    return _envelope(status_code=exception.status_code, message=message)


def _reason_phrase(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return ""


def _handle_unexpected_error(request: Request, exception: Exception) -> JSONResponse:
    """Report an unhandled failure without leaking why it happened."""
    _logger.exception(
        "Unhandled error serving %s %s", request.method, request.url.path, exc_info=exception
    )
    return _envelope(status_code=HTTP_500_INTERNAL_SERVER_ERROR, message=_UNEXPECTED_ERROR_MESSAGE)


def _envelope(
    *, status_code: int, message: str, details: list[ErrorDetail] | None = None
) -> JSONResponse:
    body = ErrorResponse(
        error=ApiError(
            code=ERROR_CODES_BY_STATUS.get(status_code, REQUEST_FAILED),
            message=message,
            details=details or [],
        )
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))
