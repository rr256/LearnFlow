"""Request and response schemas for the topic-progress endpoints (PRG-002, PRG-004).

No schema here accepts a learner identifier. The effective learner is resolved
server-side, so a client cannot record or read another learner's progress
(docs/api/conventions.md).

`learning_stage` carries the stored `snake_case` form of the five approved
stages. docs/domain/terminology.md holds the display labels a learner sees; a
client renders them, because a copy-edit to a label must not become a data
migration.

There is no way to express "clear this stage". A learner who has changed their
mind sets `not_explored`, which records that they did so on purpose. `null` is
rejected rather than treated as a clear: a stage always holds a value, which is
the same rule ADR-016 applied to `timezone` and `status`.
"""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.application.dto.topic_progress import (
    TopicProgressDetail,
    TopicProgressPage,
    TopicProgressTopic,
    TopicStageChange,
)
from app.presentation.api.schemas.pagination import Pagination


class TopicProgressTopicSchema(BaseModel):
    """The topic a progress record describes.

    `subject_id` and `curriculum_version_id` travel with it so a client showing
    the curriculum can place the record in the hierarchy it already has, without
    a second lookup.
    """

    id: uuid.UUID
    code: str | None = Field(description="Stable topic code within its subject, where one exists.")
    name: str
    is_trackable: bool = Field(
        description=(
            "Whether progress can be recorded directly against this topic. A topic that "
            "only groups subtopics cannot hold a stage of its own."
        )
    )
    subject_id: uuid.UUID
    curriculum_version_id: uuid.UUID

    @classmethod
    def of(cls, topic: TopicProgressTopic) -> TopicProgressTopicSchema:
        """Build the schema from its application DTO."""
        return cls(
            id=topic.id,
            code=topic.code,
            name=topic.name,
            is_trackable=topic.is_trackable,
            subject_id=topic.subject_id,
            curriculum_version_id=topic.curriculum_version_id,
        )


class TopicProgressSchema(BaseModel):
    """One recorded stage, with the topic it belongs to."""

    id: uuid.UUID
    learner_id: uuid.UUID
    learning_stage: str = Field(
        description=(
            "One of `not_explored`, `building_foundation`, `developing_confidence`, "
            "`practice_ready`, or `strong_understanding`. A stage guides the next action "
            "and is never a claim of permanent mastery."
        )
    )
    stage_source: str = Field(
        description=(
            "`learner` when the learner set the stage themselves. `derived` and `mixed` "
            "are reserved for stages produced from evidence; nothing produces one yet."
        )
    )
    topic: TopicProgressTopicSchema

    @classmethod
    def of(cls, detail: TopicProgressDetail) -> TopicProgressSchema:
        """Build the schema from its application DTO."""
        return cls(
            id=detail.id,
            learner_id=detail.learner_id,
            learning_stage=detail.learning_stage,
            stage_source=detail.stage_source,
            topic=TopicProgressTopicSchema.of(detail.topic),
        )


class TopicProgressResponse(BaseModel):
    """One topic-progress record, under the documented `data` envelope."""

    data: TopicProgressSchema


class TopicProgressCollectionResponse(BaseModel):
    """A page of topic-progress records, under the documented collection envelope.

    Only topics the learner has recorded something against appear. A topic that
    is absent has no stored stage, which reads as *Not explored*; listing every
    topic is what the curriculum endpoints do.
    """

    data: list[TopicProgressSchema]
    pagination: Pagination

    @classmethod
    def of(cls, page: TopicProgressPage) -> TopicProgressCollectionResponse:
        """Build the response from its application DTO."""
        return cls(
            data=[TopicProgressSchema.of(detail) for detail in page.records],
            pagination=Pagination(limit=page.limit, offset=page.offset, total=page.total),
        )


class RecordTopicStageRequest(BaseModel):
    """The stage a learner is recording against one topic.

    `learning_stage` is required and may not be null. Whether the value is one
    of the five is checked by the use case rather than by an enum here, so the
    rejection message names the accepted values once, in the layer that also
    mirrors the database `CHECK`.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    learning_stage: str = Field(
        min_length=1,
        description="The stage to record. Setting `not_explored` is how a learner resets one.",
    )

    def to_change(self) -> TopicStageChange:
        """Map the request onto the application's change structure."""
        return TopicStageChange(learning_stage=self.learning_stage)
