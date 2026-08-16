"""Request and response schemas for the learning-resource endpoints.

A separate representation from the application DTOs, so a change to the HTTP
contract does not reach back into the use case
(docs/architecture/dependency-rules.md).

Every field name is `snake_case`, per docs/api/conventions.md. No schema here
accepts a `learner_id`: the effective learner is resolved server-side.

The length bounds below are **input guards, not stored constraints**. The columns
behind them are `text`, as docs/database/schema.md specifies for learner-facing
prose; refusing an implausible field here turns a mistake into a `422` naming the
field rather than a row nobody can read.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.application.dto.resource import (
    MAX_TOPIC_LINKS,
    RESOURCE_STATUSES,
    RESOURCE_TYPES,
    NewResource,
    ResourceChanges,
    ResourceDetail,
    ResourcePage,
)
from app.presentation.api.schemas.pagination import Pagination

MAX_TITLE_LENGTH = 300
MAX_SOURCE_LABEL_LENGTH = 300
MAX_REFERENCE_LENGTH = 2000


class ResourceTopicSchema(BaseModel):
    """A topic a resource covers."""

    id: uuid.UUID
    code: str | None
    name: str
    subject_id: uuid.UUID
    subject_name: str


class ResourceSchema(BaseModel):
    """One learning resource as a learner reads it."""

    id: uuid.UUID
    owner_learner_id: uuid.UUID | None = Field(
        description=(
            "The learner this material belongs to. Null is reserved for curated or shared "
            "content, which nothing writes today."
        )
    )
    resource_type: str = Field(description=f"One of: {', '.join(RESOURCE_TYPES)}.")
    title: str = Field(description="What the learner calls this material.")
    source_label: str | None = Field(
        description=(
            "Where the material is, in the learner's own words — a book and chapter, a "
            "folder they keep, a lecture series. This is what carries material that is not "
            "on the web."
        )
    )
    external_reference: str | None = Field(
        description=(
            "An http or https address. No other scheme is accepted, so no location on the "
            "learner's own machine is stored or returned."
        )
    )
    status: str = Field(
        description=(
            f"One of: {', '.join(RESOURCE_STATUSES)}. `archived` is material the learner has "
            "put aside, and it is reversible — nothing deletes a resource."
        )
    )
    topics: list[ResourceTopicSchema] = Field(
        description=(
            "The curriculum topics this material covers, in the order they were linked. "
            "Carried on a listed resource as well as a read one, unlike a study plan's "
            "items: a link set is bounded, and naming what a resource covers is the point."
        )
    )

    @classmethod
    def of(cls, resource: ResourceDetail) -> ResourceSchema:
        """Build the schema from its application DTO."""
        return cls(
            id=resource.id,
            owner_learner_id=resource.owner_learner_id,
            resource_type=resource.resource_type,
            title=resource.title,
            source_label=resource.source_label,
            external_reference=resource.external_reference,
            status=resource.status,
            topics=[
                ResourceTopicSchema(
                    id=topic.id,
                    code=topic.code,
                    name=topic.name,
                    subject_id=topic.subject_id,
                    subject_name=topic.subject_name,
                )
                for topic in resource.topics
            ],
        )


class ResourceResponse(BaseModel):
    """One learning resource, under the documented `data` envelope."""

    data: ResourceSchema


class ResourceCollectionResponse(BaseModel):
    """A page of learning resources, with the documented pagination block."""

    data: list[ResourceSchema]
    pagination: Pagination

    @classmethod
    def of(cls, page: ResourcePage, *, limit: int, offset: int) -> ResourceCollectionResponse:
        """Build the response from the application's page."""
        return cls(
            data=[ResourceSchema.of(resource) for resource in page.resources],
            pagination=Pagination(limit=limit, offset=offset, total=page.total),
        )


class RegisterResourceRequest(BaseModel):
    """What RES-001 asks: where one piece of study material is, and what it covers.

    An unknown field is rejected rather than ignored. There is deliberately no
    `status`: every resource is written `registered`, and putting one aside is a
    later statement made through RES-004 — the shape PLN-004 uses for a plan
    item, whose status is likewise not a creation field.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    resource_type: str = Field(min_length=1, description=f"One of: {', '.join(RESOURCE_TYPES)}.")
    title: str = Field(
        min_length=1,
        max_length=MAX_TITLE_LENGTH,
        description="What you call this material, so you can find it again.",
    )
    source_label: str | None = Field(
        default=None,
        max_length=MAX_SOURCE_LABEL_LENGTH,
        description="Where the material is, in your own words.",
    )
    external_reference: str | None = Field(
        default=None,
        max_length=MAX_REFERENCE_LENGTH,
        description="A full http:// or https:// web address.",
    )
    topic_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description=(
            f"The topics this material covers, at most {MAX_TOPIC_LINKS}. A topic named "
            "twice is rejected rather than collapsed."
        ),
    )

    def to_new_resource(self) -> NewResource:
        """Map the request onto its application DTO."""
        return NewResource(
            resource_type=self.resource_type,
            title=self.title,
            source_label=self.source_label,
            external_reference=self.external_reference,
            topic_ids=tuple(self.topic_ids),
        )


class UpdateResourceRequest(BaseModel):
    """A partial update to a learning resource (RES-004).

    A field that is absent is left alone. An explicit null clears the stored
    value, which absence cannot express. The result must still say where the
    material is, in words or by a link.

    `topic_ids` follows the same absent-versus-null rule at the level of the
    whole set: absent leaves the links alone, and a supplied list replaces them
    entirely, so a topic left out of one is unlinked and an empty list unlinks
    everything. That is GOAL-005's whole-week replacement, applied to a link set.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, max_length=MAX_TITLE_LENGTH, description="A new title.")
    resource_type: str | None = Field(
        default=None, description=f"One of: {', '.join(RESOURCE_TYPES)}."
    )
    source_label: str | None = Field(
        default=None,
        max_length=MAX_SOURCE_LABEL_LENGTH,
        description="Where the material is, in your own words, or null to remove it.",
    )
    external_reference: str | None = Field(
        default=None,
        max_length=MAX_REFERENCE_LENGTH,
        description="A full http:// or https:// web address, or null to remove it.",
    )
    status: str | None = Field(
        default=None,
        description=(
            f"One of: {', '.join(RESOURCE_STATUSES)}. Archiving puts material aside and is "
            "reversible."
        ),
    )
    topic_ids: list[uuid.UUID] | None = Field(
        default=None,
        description=(
            "The topics this material covers, replaced whole. An empty list — or an explicit "
            "null — unlinks every topic; omit the field to leave the links alone."
        ),
    )

    @model_validator(mode="after")
    def _reject_nulls_that_cannot_clear(self) -> UpdateResourceRequest:
        """Three fields always hold a value, so null cannot mean "remove it".

        The rule LRN-002 applies to a timezone and GOAL-004 to a status: a
        resource always has a title, a type, and a state, so a null naming one of
        them is a client error rather than a clearance.
        """
        supplied = self.model_fields_set
        for name in ("title", "resource_type", "status"):
            if name in supplied and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null. Omit it to leave the stored value alone.")
        return self

    def to_changes(self) -> ResourceChanges:
        """Map the request onto the application's partial-update structure.

        `model_fields_set` is what distinguishes "absent" from "explicitly null";
        a default alone cannot, because both arrive as `None`.
        """
        supplied = self.model_fields_set
        return ResourceChanges(
            title=self.title if "title" in supplied else None,
            resource_type=self.resource_type if "resource_type" in supplied else None,
            source_label=self.source_label if "source_label" in supplied else None,
            clear_source_label="source_label" in supplied and self.source_label is None,
            external_reference=(
                self.external_reference if "external_reference" in supplied else None
            ),
            clear_external_reference=(
                "external_reference" in supplied and self.external_reference is None
            ),
            status=self.status if "status" in supplied else None,
            # No `clear_` flag: an empty list is a value distinct from no list,
            # so `None` can mean "absent" without making "unlink everything"
            # inexpressible -- unlike a bare label, where the two collide. An
            # explicit null unlinks every topic, exactly as `[]` does, which is
            # how GOAL-004 treats a null preference group.
            topic_ids=(tuple(self.topic_ids or ()) if "topic_ids" in supplied else None),
        )
