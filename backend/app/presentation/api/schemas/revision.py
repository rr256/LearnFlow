"""Request and response schemas for the revision endpoints.

A separate representation from the application DTOs, so a change to the HTTP
contract does not reach back into the use case
(docs/architecture/dependency-rules.md).

Every field name is `snake_case` and every date is ISO, per
docs/api/conventions.md. No schema here accepts a `learner_id`: the effective
learner is resolved server-side.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.application.dto.revision import (
    REVISION_STATUS_CHANGES,
    REVISION_STATUSES,
    REVISION_TRIGGERS,
    RevisionDetail,
    RevisionPage,
    RevisionStatusChange,
    ScheduledRevisions,
)
from app.presentation.api.schemas.pagination import Pagination


class RevisionTopicSchema(BaseModel):
    """The topic a revision recommends reviewing."""

    id: uuid.UUID
    code: str | None
    name: str
    subject_id: uuid.UUID
    subject_name: str


class RevisionSchema(BaseModel):
    """One revision as a learner reads it."""

    id: uuid.UUID
    topic: RevisionTopicSchema | None = Field(
        description=(
            "The topic to review. Null only when the topic is no longer stored, which is "
            "reported rather than hiding the learner's own record."
        )
    )
    due_on: date = Field(description="The day this topic becomes due for review.")
    scheduled_for: date | None = Field(
        description=(
            "A day named for this revision. Always null: naming one is an approved capability "
            "that nothing writes yet, so the column is carried rather than filled."
        )
    )
    status: str = Field(description=f"One of: {', '.join(REVISION_STATUSES)}.")
    trigger_type: str = Field(
        description=(
            f"Why this revision exists. One of: {', '.join(REVISION_TRIGGERS)} — finished "
            "planned work, or a review the learner completed, which is what makes it spaced."
        )
    )
    recommendation_reason: str | None = Field(
        description=(
            "The sentence written when the revision was created and never rewritten, so the "
            "record explains itself in the terms that produced its date. It describes the "
            "topic and the schedule, never the learner."
        )
    )
    completed_at: datetime | None = Field(
        description=(
            "When the learner marked the review done. Null unless `status` is `completed`, "
            "and cleared by any move off it."
        )
    )
    is_due: bool = Field(
        description=(
            "Whether this revision is owed today: its day has arrived or passed and nobody "
            "has settled it. Reported by the backend because what counts as due is a domain "
            "rule, so a client cannot disagree with it."
        )
    )

    @classmethod
    def of(cls, revision: RevisionDetail) -> RevisionSchema:
        """Build the schema from its application DTO."""
        return cls(
            id=revision.id,
            topic=(
                None
                if revision.topic is None
                else RevisionTopicSchema(
                    id=revision.topic.id,
                    code=revision.topic.code,
                    name=revision.topic.name,
                    subject_id=revision.topic.subject_id,
                    subject_name=revision.topic.subject_name,
                )
            ),
            due_on=revision.due_on,
            scheduled_for=revision.scheduled_for,
            status=revision.status,
            trigger_type=revision.trigger_type,
            recommendation_reason=revision.recommendation_reason,
            completed_at=revision.completed_at,
            is_due=revision.is_due,
        )


class RevisionResponse(BaseModel):
    """One revision, under the documented `data` envelope."""

    data: RevisionSchema


class RevisionCollectionResponse(BaseModel):
    """A page of revisions, with the documented pagination block."""

    data: list[RevisionSchema]
    pagination: Pagination

    @classmethod
    def of(cls, page: RevisionPage, *, limit: int, offset: int) -> RevisionCollectionResponse:
        """Build the response from the application's page."""
        return cls(
            data=[RevisionSchema.of(revision) for revision in page.revisions],
            pagination=Pagination(limit=limit, offset=offset, total=page.total),
        )


class UpdateRevisionRequest(BaseModel):
    """What REV-003 asks of one revision.

    Only a status, and an unknown field is rejected rather than ignored. There is
    deliberately no date and no reason: naming a day is the unwritten `scheduled`
    capability, and asking why a learner skipped a review would invite the
    product to form a view about the answer.
    """

    model_config = ConfigDict(extra="forbid")

    status: str = Field(description=f"One of: {', '.join(REVISION_STATUS_CHANGES)}.")

    def to_status_change(self) -> RevisionStatusChange:
        """Map the request onto its application DTO."""
        return RevisionStatusChange(status=self.status)


class ScheduledRevisionsSchema(BaseModel):
    """What one scheduling run produced."""

    scheduled_on: date = Field(
        description=(
            "The date the run was made for, in the learner's own timezone rather than the server's."
        )
    )
    created: list[RevisionSchema] = Field(
        description="The revisions written, each with the reason it exists."
    )
    already_scheduled_topic_count: int = Field(
        description=(
            "How many finished topics were left alone because they already have a revision "
            "waiting or one the learner has settled. A description of the run, not a score "
            "for the learner."
        )
    )
    reason: str = Field(
        description="What the run looked at, what it wrote, and what it left alone."
    )

    @classmethod
    def of(cls, scheduled: ScheduledRevisions) -> ScheduledRevisionsSchema:
        """Build the schema from its application DTO."""
        return cls(
            scheduled_on=scheduled.scheduled_on,
            created=[RevisionSchema.of(revision) for revision in scheduled.created],
            already_scheduled_topic_count=scheduled.already_scheduled_topic_count,
            reason=scheduled.reason,
        )


class ScheduleRevisionsResponse(BaseModel):
    """A scheduling run, under the documented `data` envelope."""

    data: ScheduledRevisionsSchema
