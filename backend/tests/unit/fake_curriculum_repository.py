"""An in-memory stand-in for the read-only curriculum repository port.

It stores records in insertion order and applies no ordering of its own, so a
use case that relies on the store to sort its results fails here rather than
passing by accident against a database that happened to return rows in the right
order. The one exception is the learning-program page, whose order the port owns
because a page cannot be sorted after it has been sliced.
"""

import uuid
from collections.abc import Sequence

from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
    SubjectRecord,
    TopicRecord,
    TopicRelationshipRecord,
)

ACTIVE_STATUS = "active"


class FakeCurriculumRepository:
    """Serves curriculum records from lists held in memory."""

    def __init__(
        self,
        *,
        programs: Sequence[LearningProgramRecord] = (),
        versions: Sequence[CurriculumVersionRecord] = (),
        subjects: Sequence[SubjectRecord] = (),
        topics: Sequence[TopicRecord] = (),
        relationships: Sequence[TopicRelationshipRecord] = (),
    ) -> None:
        self.programs = list(programs)
        self.versions = list(versions)
        self.subjects = list(subjects)
        self.topics = list(topics)
        self.relationships = list(relationships)

    def count_learning_programs(self) -> int:
        return len(self.programs)

    def list_learning_programs(
        self, *, limit: int, offset: int
    ) -> tuple[LearningProgramRecord, ...]:
        ordered = sorted(self.programs, key=lambda record: record.code)
        return tuple(ordered[offset : offset + limit])

    def find_learning_program(self, learning_program_id: uuid.UUID) -> LearningProgramRecord | None:
        return next((record for record in self.programs if record.id == learning_program_id), None)

    def list_active_curriculum_versions(
        self, learning_program_ids: Sequence[uuid.UUID]
    ) -> tuple[CurriculumVersionRecord, ...]:
        wanted = set(learning_program_ids)
        return tuple(
            record
            for record in self.versions
            if record.learning_program_id in wanted and record.status == ACTIVE_STATUS
        )

    def find_curriculum_version(
        self, curriculum_version_id: uuid.UUID
    ) -> CurriculumVersionRecord | None:
        return next(
            (record for record in self.versions if record.id == curriculum_version_id), None
        )

    def list_subjects(self, curriculum_version_id: uuid.UUID) -> tuple[SubjectRecord, ...]:
        return tuple(
            record
            for record in self.subjects
            if record.curriculum_version_id == curriculum_version_id
        )

    def list_topics(self, curriculum_version_id: uuid.UUID) -> tuple[TopicRecord, ...]:
        subject_ids = {
            record.id
            for record in self.subjects
            if record.curriculum_version_id == curriculum_version_id
        }
        return tuple(record for record in self.topics if record.subject_id in subject_ids)

    def list_topic_relationships(
        self, curriculum_version_id: uuid.UUID
    ) -> tuple[TopicRelationshipRecord, ...]:
        topic_ids = {record.id for record in self.list_topics(curriculum_version_id)}
        return tuple(record for record in self.relationships if record.source_topic_id in topic_ids)
