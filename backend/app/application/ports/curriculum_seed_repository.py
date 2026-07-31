"""The persistence port the curriculum seed use case works through.

The records below are application-owned values, not ORM rows: an implementation
maps them to whatever it stores. Every identifier is supplied by the caller
rather than returned by the store, so the use case can assemble a whole
curriculum -- subjects, topics, and the relationships between them -- before any
of it is written.

The port offers storage primitives only. Deciding what counts as a change, what
to insert, and what to leave alone belongs to the use case; infrastructure must
not make those calls on its own (docs/architecture/dependency-rules.md).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LearningProgramRecord:
    """A stored learning program."""

    id: uuid.UUID
    code: str
    name: str
    description: str | None


@dataclass(frozen=True, slots=True)
class CurriculumVersionRecord:
    """A stored curriculum version."""

    id: uuid.UUID
    learning_program_id: uuid.UUID
    version_label: str
    status: str
    source_reference: str | None
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class SubjectRecord:
    """A stored subject."""

    id: uuid.UUID
    curriculum_version_id: uuid.UUID
    code: str
    name: str
    description: str | None
    position: int


@dataclass(frozen=True, slots=True)
class TopicRecord:
    """A stored topic, root or nested."""

    id: uuid.UUID
    subject_id: uuid.UUID
    parent_topic_id: uuid.UUID | None
    code: str | None
    name: str
    description: str | None
    position: int
    is_trackable: bool


@dataclass(frozen=True, slots=True)
class TopicRelationshipRecord:
    """A stored edge between two topics."""

    source_topic_id: uuid.UUID
    target_topic_id: uuid.UUID
    relationship_type: str


class CurriculumSeedRepository(Protocol):
    """Reads and writes the curriculum records a seed run touches."""

    def find_learning_program(self, code: str) -> LearningProgramRecord | None:
        """The program with this code, or None."""
        ...

    def add_learning_program(self, record: LearningProgramRecord) -> None:
        """Store a new learning program."""
        ...

    def update_learning_program(self, record: LearningProgramRecord) -> None:
        """Overwrite the stored program identified by ``record.id``."""
        ...

    def find_curriculum_version(
        self, *, learning_program_id: uuid.UUID, version_label: str
    ) -> CurriculumVersionRecord | None:
        """The program's version carrying this label, or None."""
        ...

    def find_active_curriculum_version(
        self, learning_program_id: uuid.UUID
    ) -> CurriculumVersionRecord | None:
        """The program's active version, or None.

        At most one can exist: a partial unique index enforces it (ADR-011).
        """
        ...

    def add_curriculum_version(self, record: CurriculumVersionRecord) -> None:
        """Store a new curriculum version."""
        ...

    def update_curriculum_version(self, record: CurriculumVersionRecord) -> None:
        """Overwrite the stored version identified by ``record.id``."""
        ...

    def list_subjects(self, curriculum_version_id: uuid.UUID) -> tuple[SubjectRecord, ...]:
        """Every subject of this version."""
        ...

    def add_subject(self, record: SubjectRecord) -> None:
        """Store a new subject."""
        ...

    def update_subject(self, record: SubjectRecord) -> None:
        """Overwrite the stored subject identified by ``record.id``."""
        ...

    def vacate_subject_positions(self, curriculum_version_id: uuid.UUID) -> None:
        """Move this version's subjects to positions no final position can collide with.

        ``(curriculum_version_id, position)`` is unique and checked per
        statement, so re-ordering subjects one update at a time trips the
        constraint the moment two subjects swap places. Emptying the range first
        makes the order of the updates that follow irrelevant.
        """
        ...

    def list_topics(self, curriculum_version_id: uuid.UUID) -> tuple[TopicRecord, ...]:
        """Every topic under every subject of this version, at any depth."""
        ...

    def add_topic(self, record: TopicRecord) -> None:
        """Store a new topic."""
        ...

    def update_topic(self, record: TopicRecord) -> None:
        """Overwrite the stored topic identified by ``record.id``."""
        ...

    def list_topic_relationships(
        self, curriculum_version_id: uuid.UUID
    ) -> tuple[TopicRelationshipRecord, ...]:
        """Every relationship whose source topic belongs to this version."""
        ...

    def add_topic_relationship(self, record: TopicRelationshipRecord) -> None:
        """Store a new topic relationship."""
        ...

    def flush(self) -> None:
        """Send pending writes to the store without ending the transaction.

        The use case calls this where one statement must land before the next,
        which the store cannot infer -- vacating subject positions before
        re-assigning them, above all.
        """
        ...
