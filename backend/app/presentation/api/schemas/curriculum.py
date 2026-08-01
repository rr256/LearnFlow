"""Response schemas for the curriculum endpoints (CUR-001 to CUR-003).

Each schema is built from an application DTO by an explicit constructor rather
than by attribute inference, so adding a field to a DTO cannot silently widen
the public contract (docs/architecture/dependency-rules.md).

Field names are `snake_case`, identifiers are UUID strings, and timestamps carry
their timezone, per docs/api/conventions.md.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.application.dto.curriculum import (
    CurriculumTree,
    CurriculumVersionReference,
    LearningProgramPage,
    LearningProgramSummary,
    SubjectNode,
    TopicNode,
    TopicRelationshipEdge,
)
from app.presentation.api.schemas.pagination import Pagination


class CurriculumVersionSchema(BaseModel):
    """A curriculum version, named well enough to request its tree."""

    id: uuid.UUID
    learning_program_id: uuid.UUID
    version_label: str = Field(description="Human-readable version, such as `2027`.")
    status: str = Field(description="One of `draft`, `active`, or `retired`.")
    source_reference: str | None = Field(
        description="Official or curator reference the version was transcribed from."
    )
    published_at: datetime | None = Field(description="When the version became active.")

    @classmethod
    def of(cls, reference: CurriculumVersionReference) -> CurriculumVersionSchema:
        """Build the schema from its application DTO."""
        return cls(
            id=reference.id,
            learning_program_id=reference.learning_program_id,
            version_label=reference.version_label,
            status=reference.status,
            source_reference=reference.source_reference,
            published_at=reference.published_at,
        )


class LearningProgramSchema(BaseModel):
    """A learning program and the curriculum version currently active for it."""

    id: uuid.UUID
    code: str = Field(description="Stable program code, such as `gate-cse`.")
    name: str
    description: str | None
    active_curriculum_version: CurriculumVersionSchema | None = Field(
        description="Null while the program has only draft or retired versions."
    )

    @classmethod
    def of(cls, summary: LearningProgramSummary) -> LearningProgramSchema:
        """Build the schema from its application DTO."""
        return cls(
            id=summary.id,
            code=summary.code,
            name=summary.name,
            description=summary.description,
            active_curriculum_version=(
                None
                if summary.active_curriculum_version is None
                else CurriculumVersionSchema.of(summary.active_curriculum_version)
            ),
        )


class TopicSchema(BaseModel):
    """A topic, with any subtopics nested beneath it."""

    id: uuid.UUID
    code: str | None = Field(
        description="Stable code within the subject, where the syllabus uses one."
    )
    name: str
    description: str | None
    position: int = Field(description="Recommended order within its parent.")
    is_trackable: bool = Field(
        description="Whether learner progress can be recorded directly against this topic."
    )
    subtopics: list[TopicSchema]

    @classmethod
    def of(cls, node: TopicNode) -> TopicSchema:
        """Build the schema from its application DTO."""
        return cls(
            id=node.id,
            code=node.code,
            name=node.name,
            description=node.description,
            position=node.position,
            is_trackable=node.is_trackable,
            subtopics=[cls.of(subtopic) for subtopic in node.subtopics],
        )


class SubjectSchema(BaseModel):
    """A subject and its root topics, in recommended order."""

    id: uuid.UUID
    code: str = Field(description="Stable subject code within the curriculum version.")
    name: str
    description: str | None
    position: int = Field(description="Recommended order within the curriculum version.")
    topics: list[TopicSchema]

    @classmethod
    def of(cls, node: SubjectNode) -> SubjectSchema:
        """Build the schema from its application DTO."""
        return cls(
            id=node.id,
            code=node.code,
            name=node.name,
            description=node.description,
            position=node.position,
            topics=[TopicSchema.of(topic) for topic in node.topics],
        )


class TopicRelationshipSchema(BaseModel):
    """A prerequisite or sequencing edge between two topics of this version."""

    source_topic_id: uuid.UUID
    target_topic_id: uuid.UUID
    relationship_type: str = Field(
        description="One of `prerequisite`, `recommended_before`, or `related`."
    )

    @classmethod
    def of(cls, edge: TopicRelationshipEdge) -> TopicRelationshipSchema:
        """Build the schema from its application DTO."""
        return cls(
            source_topic_id=edge.source_topic_id,
            target_topic_id=edge.target_topic_id,
            relationship_type=edge.relationship_type,
        )


class CurriculumTreeSchema(BaseModel):
    """One curriculum version's full hierarchy.

    Relationships are listed beside the tree rather than inlined on a topic: an
    edge relates two topics, and nesting it under one would make the tree assert
    which end owns it.
    """

    curriculum_version: CurriculumVersionSchema
    subjects: list[SubjectSchema]
    topic_relationships: list[TopicRelationshipSchema]

    @classmethod
    def of(cls, tree: CurriculumTree) -> CurriculumTreeSchema:
        """Build the schema from its application DTO."""
        return cls(
            curriculum_version=CurriculumVersionSchema.of(tree.curriculum_version),
            subjects=[SubjectSchema.of(subject) for subject in tree.subjects],
            topic_relationships=[
                TopicRelationshipSchema.of(edge) for edge in tree.topic_relationships
            ],
        )


class LearningProgramResponse(BaseModel):
    """One learning program, under the documented `data` envelope."""

    data: LearningProgramSchema


class LearningProgramCollectionResponse(BaseModel):
    """A page of learning programs, under the documented collection envelope."""

    data: list[LearningProgramSchema]
    pagination: Pagination

    @classmethod
    def of(cls, page: LearningProgramPage) -> LearningProgramCollectionResponse:
        """Build the response from its application DTO."""
        return cls(
            data=[LearningProgramSchema.of(summary) for summary in page.programs],
            pagination=Pagination(limit=page.limit, offset=page.offset, total=page.total),
        )


class CurriculumTreeResponse(BaseModel):
    """One curriculum hierarchy, under the documented `data` envelope."""

    data: CurriculumTreeSchema
