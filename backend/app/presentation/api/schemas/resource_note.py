"""Request and response schemas for the resource-note endpoints.

A separate representation from the application DTOs, so a change to the HTTP
contract does not reach back into the use case
(docs/architecture/dependency-rules.md).

Every field name is `snake_case`, per docs/api/conventions.md. No schema here
accepts a `learner_id`: the effective learner is resolved server-side, and a note
is reached through the resource whose owner they must be.

`body` carries the learner's own text and is returned **exactly as stored**.
Nothing here truncates it, summarises it, strips its line breaks, or marks it up:
what a learner wrote is what they read back.

The length bounds below mirror the application's, so an over-long field is a
`422` naming the field before the use case is entered. Neither refusal echoes the
rejected text — the rule docs/api/conventions.md states for every value, and the
one field in the product where it matters most.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.application.dto.resource_note import (
    MAX_NOTE_BODY_LENGTH,
    MAX_NOTE_TITLE_LENGTH,
    RESOURCE_NOTE_STATUSES,
    NewResourceNote,
    ResourceNoteChanges,
    ResourceNoteDetail,
    ResourceNotePage,
)
from app.presentation.api.schemas.pagination import Pagination


class ResourceNoteSchema(BaseModel):
    """One resource note as a learner reads it."""

    id: uuid.UUID
    resource_id: uuid.UUID = Field(
        description=(
            "The study material this note was written against. A note covers the topics "
            "that resource covers and carries none of its own."
        )
    )
    title: str = Field(description="What the learner calls this note.")
    body: str = Field(
        description=(
            "What the learner wrote or pasted, exactly as they stored it. Plain text: "
            "nothing here is markup, and nothing renders it as any."
        )
    )
    status: str = Field(
        description=(
            f"One of: {', '.join(RESOURCE_NOTE_STATUSES)}. `archived` is a note the learner "
            "has put aside, and it is reversible — nothing deletes a note."
        )
    )

    @classmethod
    def of(cls, note: ResourceNoteDetail) -> ResourceNoteSchema:
        """Build the schema from its application DTO."""
        return cls(
            id=note.id,
            resource_id=note.resource_id,
            title=note.title,
            body=note.body,
            status=note.status,
        )


class ResourceNoteResponse(BaseModel):
    """One resource note, under the documented `data` envelope."""

    data: ResourceNoteSchema


class ResourceNoteCollectionResponse(BaseModel):
    """A page of resource notes, with the documented pagination block."""

    data: list[ResourceNoteSchema]
    pagination: Pagination

    @classmethod
    def of(
        cls, page: ResourceNotePage, *, limit: int, offset: int
    ) -> ResourceNoteCollectionResponse:
        """Build the response from the application's page."""
        return cls(
            data=[ResourceNoteSchema.of(note) for note in page.notes],
            pagination=Pagination(limit=limit, offset=offset, total=page.total),
        )


class WriteResourceNoteRequest(BaseModel):
    """What RES-009 asks: one note to keep against a piece of study material.

    An unknown field is rejected rather than ignored. There is deliberately no
    `status`: every note is written `active`, and putting one aside is a later
    statement made through RES-012 — the shape RES-001 uses for a resource.

    There is no `resource_id` either. It is named by the path, so a body cannot
    disagree with the resource whose ownership was just checked.

    **`body` is not whitespace-stripped by the model.** `str_strip_whitespace` is
    deliberately off here, unlike every other request schema: it would strip the
    leading indentation of a pasted code block or the trailing blank line of a
    transcribed passage. The use case removes surrounding whitespace and nothing
    else, so the learner's own line breaks and spacing survive.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        min_length=1,
        max_length=MAX_NOTE_TITLE_LENGTH,
        description="What you call this note, so you can find it again without opening it.",
    )
    body: str = Field(
        min_length=1,
        max_length=MAX_NOTE_BODY_LENGTH,
        description=(
            "What you want to keep — your own notes, or a passage you have copied out. "
            f"At most {MAX_NOTE_BODY_LENGTH} characters. Stored as plain text and kept "
            "on this machine: it is not sent anywhere and nothing reads it."
        ),
    )

    def to_new_note(self) -> NewResourceNote:
        """Map the request onto its application DTO."""
        return NewResourceNote(title=self.title, body=self.body)


class UpdateResourceNoteRequest(BaseModel):
    """A partial update to a resource note (RES-012).

    A field that is absent is left alone. **No field may be null**: a note always
    has a title, a body, and a status, so a null naming one of them is a client
    error rather than a clearance — the rule LRN-002 applies to a timezone,
    GOAL-004 to a status, and RES-004 to a resource's title.

    A note is corrected **in place**, however many times the learner likes.
    Nothing reads a note, so no stored record can be made to disagree with a
    correction — the condition ADR-035 could not meet for a question a quiz had
    already asked.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None, max_length=MAX_NOTE_TITLE_LENGTH, description="A new title."
    )
    body: str | None = Field(
        default=None,
        max_length=MAX_NOTE_BODY_LENGTH,
        description="The note's text, replaced whole.",
    )
    status: str | None = Field(
        default=None,
        description=(
            f"One of: {', '.join(RESOURCE_NOTE_STATUSES)}. Putting a note aside is "
            "reversible and destroys nothing."
        ),
    )

    @model_validator(mode="after")
    def _reject_nulls(self) -> UpdateResourceNoteRequest:
        """Every field here always holds a value, so null cannot mean "remove it"."""
        supplied = self.model_fields_set
        for name in ("title", "body", "status"):
            if name in supplied and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null. Omit it to leave the stored value alone.")
        return self

    def to_changes(self) -> ResourceNoteChanges:
        """Map the request onto the application's partial-update structure."""
        return ResourceNoteChanges(title=self.title, body=self.body, status=self.status)
