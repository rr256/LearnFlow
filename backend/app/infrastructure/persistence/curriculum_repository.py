"""SQLAlchemy implementation of the read-only curriculum repository port.

Maps the curriculum ORM models onto the plain application records the use case
works with. It fetches rows and nothing more: nesting subtopics, ordering by
position, and deciding what a missing record means all belong to the use case
(docs/architecture/dependency-rules.md).

Nothing here commits or writes. The session's transaction is owned by the
caller, which for an HTTP request is the composition root that opened it.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
    SubjectRecord,
    TopicRecord,
    TopicRelationshipRecord,
)
from app.infrastructure.persistence.curriculum import (
    CurriculumVersion,
    LearningProgram,
    Subject,
    Topic,
    TopicRelationship,
)

ACTIVE_STATUS = "active"


class SqlAlchemyCurriculumRepository:
    """Reads the curriculum hierarchy through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one unit of work."""
        self._session = session

    def count_learning_programs(self) -> int:
        """How many learning programs are stored, ignoring any page window."""
        return self._session.scalar(select(func.count()).select_from(LearningProgram)) or 0

    def list_learning_programs(
        self, *, limit: int, offset: int
    ) -> tuple[LearningProgramRecord, ...]:
        """One page of learning programs, ordered by `code`.

        `code` is unique and stable, so the same offset returns the same rows
        across requests; ordering by name would not, because two programs may
        share one.
        """
        models = self._session.scalars(
            select(LearningProgram).order_by(LearningProgram.code).limit(limit).offset(offset)
        )
        return tuple(_program_record(model) for model in models)

    def find_learning_program(self, learning_program_id: uuid.UUID) -> LearningProgramRecord | None:
        """The program with this identifier, or None."""
        model = self._session.get(LearningProgram, learning_program_id)
        return None if model is None else _program_record(model)

    def list_active_curriculum_versions(
        self, learning_program_ids: Sequence[uuid.UUID]
    ) -> tuple[CurriculumVersionRecord, ...]:
        """The active curriculum version of each program named, where one exists."""
        if not learning_program_ids:
            return ()
        models = self._session.scalars(
            select(CurriculumVersion).where(
                CurriculumVersion.learning_program_id.in_(learning_program_ids),
                CurriculumVersion.status == ACTIVE_STATUS,
            )
        )
        return tuple(_version_record(model) for model in models)

    def find_curriculum_version(
        self, curriculum_version_id: uuid.UUID
    ) -> CurriculumVersionRecord | None:
        """The curriculum version with this identifier, or None."""
        model = self._session.get(CurriculumVersion, curriculum_version_id)
        return None if model is None else _version_record(model)

    def list_subjects(self, curriculum_version_id: uuid.UUID) -> tuple[SubjectRecord, ...]:
        """Every subject of this version."""
        models = self._session.scalars(
            select(Subject)
            .where(Subject.curriculum_version_id == curriculum_version_id)
            .order_by(Subject.position)
        )
        return tuple(_subject_record(model) for model in models)

    def list_topics(self, curriculum_version_id: uuid.UUID) -> tuple[TopicRecord, ...]:
        """Every topic under every subject of this version, at any depth."""
        models = self._session.scalars(
            select(Topic)
            .join(Subject, Topic.subject_id == Subject.id)
            .where(Subject.curriculum_version_id == curriculum_version_id)
            .order_by(Subject.position, Topic.position)
        )
        return tuple(_topic_record(model) for model in models)

    def list_topic_relationships(
        self, curriculum_version_id: uuid.UUID
    ) -> tuple[TopicRelationshipRecord, ...]:
        """Every relationship whose source topic belongs to this version."""
        models = self._session.scalars(
            select(TopicRelationship)
            .join(Topic, TopicRelationship.source_topic_id == Topic.id)
            .join(Subject, Topic.subject_id == Subject.id)
            .where(Subject.curriculum_version_id == curriculum_version_id)
            .order_by(TopicRelationship.relationship_type)
        )
        return tuple(
            TopicRelationshipRecord(
                source_topic_id=model.source_topic_id,
                target_topic_id=model.target_topic_id,
                relationship_type=model.relationship_type,
            )
            for model in models
        )


def _program_record(model: LearningProgram) -> LearningProgramRecord:
    return LearningProgramRecord(
        id=model.id,
        code=model.code,
        name=model.name,
        description=model.description,
    )


def _version_record(model: CurriculumVersion) -> CurriculumVersionRecord:
    return CurriculumVersionRecord(
        id=model.id,
        learning_program_id=model.learning_program_id,
        version_label=model.version_label,
        status=model.status,
        source_reference=model.source_reference,
        published_at=model.published_at,
    )


def _subject_record(model: Subject) -> SubjectRecord:
    return SubjectRecord(
        id=model.id,
        curriculum_version_id=model.curriculum_version_id,
        code=model.code,
        name=model.name,
        description=model.description,
        position=model.position,
    )


def _topic_record(model: Topic) -> TopicRecord:
    return TopicRecord(
        id=model.id,
        subject_id=model.subject_id,
        parent_topic_id=model.parent_topic_id,
        code=model.code,
        name=model.name,
        description=model.description,
        position=model.position,
        is_trackable=model.is_trackable,
    )
