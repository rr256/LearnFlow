"""SQLAlchemy implementation of the curriculum seed repository port.

Maps the application's plain records onto the curriculum ORM models and back.
It stores what it is told: which records to write, and whether a difference
counts as a change, are decided by the use case
(docs/architecture/dependency-rules.md).

The session's transaction is owned by the caller. Nothing here commits, so a
seed run that fails half way leaves no partial curriculum behind.
"""

import uuid

from sqlalchemy import select, update
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


class SqlAlchemyCurriculumSeedRepository:
    """Reads and writes curriculum records through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one unit of work."""
        self._session = session

    # -- learning program ---------------------------------------------------

    def find_learning_program(self, code: str) -> LearningProgramRecord | None:
        """The program with this code, or None."""
        model = self._session.scalar(select(LearningProgram).where(LearningProgram.code == code))
        return None if model is None else _program_record(model)

    def add_learning_program(self, record: LearningProgramRecord) -> None:
        """Store a new learning program."""
        self._session.add(
            LearningProgram(
                id=record.id,
                code=record.code,
                name=record.name,
                description=record.description,
            )
        )

    def update_learning_program(self, record: LearningProgramRecord) -> None:
        """Overwrite the stored program identified by ``record.id``."""
        model = self._session.get(LearningProgram, record.id)
        if model is None:
            raise LookupError(f"Learning program {record.id} is not stored.")
        model.name = record.name
        model.description = record.description

    # -- curriculum version -------------------------------------------------

    def find_curriculum_version(
        self, *, learning_program_id: uuid.UUID, version_label: str
    ) -> CurriculumVersionRecord | None:
        """The program's version carrying this label, or None."""
        model = self._session.scalar(
            select(CurriculumVersion).where(
                CurriculumVersion.learning_program_id == learning_program_id,
                CurriculumVersion.version_label == version_label,
            )
        )
        return None if model is None else _version_record(model)

    def find_active_curriculum_version(
        self, learning_program_id: uuid.UUID
    ) -> CurriculumVersionRecord | None:
        """The program's active version, or None."""
        model = self._session.scalar(
            select(CurriculumVersion).where(
                CurriculumVersion.learning_program_id == learning_program_id,
                CurriculumVersion.status == "active",
            )
        )
        return None if model is None else _version_record(model)

    def add_curriculum_version(self, record: CurriculumVersionRecord) -> None:
        """Store a new curriculum version."""
        self._session.add(
            CurriculumVersion(
                id=record.id,
                learning_program_id=record.learning_program_id,
                version_label=record.version_label,
                status=record.status,
                source_reference=record.source_reference,
                published_at=record.published_at,
            )
        )

    def update_curriculum_version(self, record: CurriculumVersionRecord) -> None:
        """Overwrite the stored version identified by ``record.id``."""
        model = self._session.get(CurriculumVersion, record.id)
        if model is None:
            raise LookupError(f"Curriculum version {record.id} is not stored.")
        model.status = record.status
        model.source_reference = record.source_reference
        model.published_at = record.published_at

    # -- subjects -----------------------------------------------------------

    def list_subjects(self, curriculum_version_id: uuid.UUID) -> tuple[SubjectRecord, ...]:
        """Every subject of this version."""
        models = self._session.scalars(
            select(Subject)
            .where(Subject.curriculum_version_id == curriculum_version_id)
            .order_by(Subject.position)
        )
        return tuple(_subject_record(model) for model in models)

    def add_subject(self, record: SubjectRecord) -> None:
        """Store a new subject."""
        self._session.add(
            Subject(
                id=record.id,
                curriculum_version_id=record.curriculum_version_id,
                code=record.code,
                name=record.name,
                description=record.description,
                position=record.position,
            )
        )

    def update_subject(self, record: SubjectRecord) -> None:
        """Overwrite the stored subject identified by ``record.id``."""
        model = self._session.get(Subject, record.id)
        if model is None:
            raise LookupError(f"Subject {record.id} is not stored.")
        model.code = record.code
        model.name = record.name
        model.description = record.description
        model.position = record.position

    def vacate_subject_positions(self, curriculum_version_id: uuid.UUID) -> None:
        """Move this version's subjects out of the positive position range.

        ``-position - 1`` is injective over the positive positions the seed
        assigns, so the moved rows stay unique among themselves while leaving
        every target position free.
        """
        self._session.execute(
            update(Subject)
            .where(Subject.curriculum_version_id == curriculum_version_id)
            .values(position=-Subject.position - 1)
        )

    # -- topics -------------------------------------------------------------

    def list_topics(self, curriculum_version_id: uuid.UUID) -> tuple[TopicRecord, ...]:
        """Every topic under every subject of this version, at any depth."""
        models = self._session.scalars(
            select(Topic)
            .join(Subject, Topic.subject_id == Subject.id)
            .where(Subject.curriculum_version_id == curriculum_version_id)
            .order_by(Subject.position, Topic.position)
        )
        return tuple(_topic_record(model) for model in models)

    def add_topic(self, record: TopicRecord) -> None:
        """Store a new topic."""
        self._session.add(
            Topic(
                id=record.id,
                subject_id=record.subject_id,
                parent_topic_id=record.parent_topic_id,
                code=record.code,
                name=record.name,
                description=record.description,
                position=record.position,
                is_trackable=record.is_trackable,
            )
        )

    def update_topic(self, record: TopicRecord) -> None:
        """Overwrite the stored topic identified by ``record.id``."""
        model = self._session.get(Topic, record.id)
        if model is None:
            raise LookupError(f"Topic {record.id} is not stored.")
        model.subject_id = record.subject_id
        model.parent_topic_id = record.parent_topic_id
        model.code = record.code
        model.name = record.name
        model.description = record.description
        model.position = record.position
        model.is_trackable = record.is_trackable

    # -- topic relationships ------------------------------------------------

    def list_topic_relationships(
        self, curriculum_version_id: uuid.UUID
    ) -> tuple[TopicRelationshipRecord, ...]:
        """Every relationship whose source topic belongs to this version."""
        models = self._session.scalars(
            select(TopicRelationship)
            .join(Topic, TopicRelationship.source_topic_id == Topic.id)
            .join(Subject, Topic.subject_id == Subject.id)
            .where(Subject.curriculum_version_id == curriculum_version_id)
        )
        return tuple(
            TopicRelationshipRecord(
                source_topic_id=model.source_topic_id,
                target_topic_id=model.target_topic_id,
                relationship_type=model.relationship_type,
            )
            for model in models
        )

    def add_topic_relationship(self, record: TopicRelationshipRecord) -> None:
        """Store a new topic relationship."""
        self._session.add(
            TopicRelationship(
                source_topic_id=record.source_topic_id,
                target_topic_id=record.target_topic_id,
                relationship_type=record.relationship_type,
            )
        )

    # -- unit of work -------------------------------------------------------

    def flush(self) -> None:
        """Send pending writes to the database without committing."""
        self._session.flush()


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
