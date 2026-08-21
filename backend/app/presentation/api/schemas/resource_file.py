"""Request and response schemas for a resource's PDF files (RES-014 to RES-017).

A separate representation from the application DTOs, so a change to the HTTP
contract does not reach back into the use case
(docs/architecture/dependency-rules.md).

Every field name is `snake_case`, per docs/api/conventions.md. No schema here
accepts a `learner_id`: the effective learner is resolved server-side, and a file
is reachable only through a resource they own.

**`storage_key` appears in no schema in this module.** It is where the bytes are,
and docs/api/endpoints.md forbids a resource endpoint from returning a storage
location or a filesystem path. Keeping it out of the response models is what makes
that true by construction rather than by remembering to strip it.

**No figure here measures the learner.** `byte_size` and `page_count` describe a
document; neither is totalled across files, ranked, or shown as progress.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.application.dto.resource_file import (
    MAX_FILE_BYTES,
    MAX_FILES_PER_RESOURCE,
    MAX_PAGE_COUNT,
    RESOURCE_FILE_STATUSES,
    ResourceFileRecord,
)


class ResourceFileSchema(BaseModel):
    """One PDF stored against a resource."""

    id: uuid.UUID = Field(description="The stored file, and the only way to name it.")
    resource_id: uuid.UUID = Field(description="The material it belongs to.")
    original_filename: str = Field(
        description=(
            "What the learner called the file. Offered back on download so they "
            "recognise it. **Not a path**: it never named a location on their "
            "machine and never names one on the server."
        )
    )
    byte_size: int = Field(description="How large the file is, in bytes.")
    page_count: int = Field(description="How many pages the PDF has.")
    content_type: str = Field(
        description="Always `application/pdf`, decided from what LearnFlow validated."
    )
    checksum: str = Field(description="SHA-256 of the stored bytes, so corruption is detectable.")
    status: str = Field(
        description=(
            "`active` or `archived`. Archiving hides a file from the catalogue "
            "and **removes nothing** — it is reversible, and the bytes stay."
        )
    )
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def of(cls, record: ResourceFileRecord) -> ResourceFileSchema:
        """Build the schema from its application DTO.

        `storage_key` is **not** copied across. That omission is the contract.
        """
        return cls(
            id=record.id,
            resource_id=record.resource_id,
            original_filename=record.original_filename,
            byte_size=record.byte_size,
            page_count=record.page_count,
            content_type=record.content_type,
            checksum=record.checksum,
            status=record.status,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class UpdateResourceFileRequest(BaseModel):
    """What RES-017 asks: set a stored file aside, or bring it back.

    `status` is the only field. Nothing else about a stored file may move: its
    name, size, page count, and checksum all describe bytes that have not
    changed, so accepting a new value for any of them would let the row disagree
    with what is on disk.
    """

    model_config = {"extra": "forbid"}

    status: str = Field(
        description=f"One of {', '.join(RESOURCE_FILE_STATUSES)}.",
    )


class ResourceFileResponse(BaseModel):
    """One stored file, under the documented `data` envelope."""

    data: ResourceFileSchema


class ResourceFileCollectionResponse(BaseModel):
    """A resource's stored files, newest first, under the `data` envelope.

    There is deliberately **no pagination block**: a resource holds at most
    `MAX_FILES_PER_RESOURCE` files, so the collection is bounded by a rule rather
    than by a page, and every file is always reachable in one read.
    """

    data: list[ResourceFileSchema]


FILE_LIMITS: dict[str, int] = {
    "max_file_bytes": MAX_FILE_BYTES,
    "max_page_count": MAX_PAGE_COUNT,
    "max_files_per_resource": MAX_FILES_PER_RESOURCE,
}
"""The limits this endpoint enforces, for the route's documentation.

Exposed in the OpenAPI description rather than in a response: a learner is told
what they may add, not how much of an allowance they have left.
"""
