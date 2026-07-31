"""An in-memory stand-in for the curriculum seed repository port.

It enforces the uniqueness rules the real schema enforces -- one active version
per program, one subject per position -- so a use case that would trip a
database constraint trips this fake instead, without needing PostgreSQL.
"""

import uuid

from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
    SubjectRecord,
    TopicRecord,
    TopicRelationshipRecord,
)


class FakeCurriculumSeedRepository:
    """Stores curriculum records in dictionaries and records what was called."""

    def __init__(self) -> None:
        self.programs: dict[uuid.UUID, LearningProgramRecord] = {}
        self.versions: dict[uuid.UUID, CurriculumVersionRecord] = {}
        self.subjects: dict[uuid.UUID, SubjectRecord] = {}
        self.topics: dict[uuid.UUID, TopicRecord] = {}
        self.relationships: dict[tuple[uuid.UUID, uuid.UUID, str], TopicRelationshipRecord] = {}
        self.vacate_calls: list[uuid.UUID] = []
        self.flush_calls = 0

    # -- learning program ---------------------------------------------------

    def find_learning_program(self, code: str) -> LearningProgramRecord | None:
        return next((record for record in self.programs.values() if record.code == code), None)

    def add_learning_program(self, record: LearningProgramRecord) -> None:
        if self.find_learning_program(record.code) is not None:
            raise AssertionError(f"learning program code {record.code!r} is already stored")
        self.programs[record.id] = record

    def update_learning_program(self, record: LearningProgramRecord) -> None:
        self._require(record.id in self.programs, f"learning program {record.id}")
        self.programs[record.id] = record

    # -- curriculum version -------------------------------------------------

    def find_curriculum_version(
        self, *, learning_program_id: uuid.UUID, version_label: str
    ) -> CurriculumVersionRecord | None:
        return next(
            (
                record
                for record in self.versions.values()
                if record.learning_program_id == learning_program_id
                and record.version_label == version_label
            ),
            None,
        )

    def find_active_curriculum_version(
        self, learning_program_id: uuid.UUID
    ) -> CurriculumVersionRecord | None:
        return next(
            (
                record
                for record in self.versions.values()
                if record.learning_program_id == learning_program_id and record.status == "active"
            ),
            None,
        )

    def add_curriculum_version(self, record: CurriculumVersionRecord) -> None:
        self._check_single_active(record)
        self.versions[record.id] = record

    def update_curriculum_version(self, record: CurriculumVersionRecord) -> None:
        self._require(record.id in self.versions, f"curriculum version {record.id}")
        self._check_single_active(record)
        self.versions[record.id] = record

    def _check_single_active(self, record: CurriculumVersionRecord) -> None:
        if record.status != "active":
            return
        rival = self.find_active_curriculum_version(record.learning_program_id)
        if rival is not None and rival.id != record.id:
            raise AssertionError(
                f"learning program {record.learning_program_id} already has an active version"
            )

    # -- subjects -----------------------------------------------------------

    def list_subjects(self, curriculum_version_id: uuid.UUID) -> tuple[SubjectRecord, ...]:
        return tuple(
            sorted(
                (
                    record
                    for record in self.subjects.values()
                    if record.curriculum_version_id == curriculum_version_id
                ),
                key=lambda record: record.position,
            )
        )

    def add_subject(self, record: SubjectRecord) -> None:
        self._check_subject_position(record)
        self.subjects[record.id] = record

    def update_subject(self, record: SubjectRecord) -> None:
        self._require(record.id in self.subjects, f"subject {record.id}")
        self._check_subject_position(record)
        self.subjects[record.id] = record

    def _check_subject_position(self, record: SubjectRecord) -> None:
        clash = next(
            (
                other
                for other in self.subjects.values()
                if other.curriculum_version_id == record.curriculum_version_id
                and other.position == record.position
                and other.id != record.id
            ),
            None,
        )
        if clash is not None:
            raise AssertionError(
                f"subject position {record.position} is already taken by {clash.code!r}"
            )

    def vacate_subject_positions(self, curriculum_version_id: uuid.UUID) -> None:
        self.vacate_calls.append(curriculum_version_id)
        for key, record in list(self.subjects.items()):
            if record.curriculum_version_id == curriculum_version_id:
                self.subjects[key] = SubjectRecord(
                    id=record.id,
                    curriculum_version_id=record.curriculum_version_id,
                    code=record.code,
                    name=record.name,
                    description=record.description,
                    position=-record.position - 1,
                )

    # -- topics -------------------------------------------------------------

    def list_topics(self, curriculum_version_id: uuid.UUID) -> tuple[TopicRecord, ...]:
        subject_ids = {record.id for record in self.list_subjects(curriculum_version_id)}
        return tuple(record for record in self.topics.values() if record.subject_id in subject_ids)

    def add_topic(self, record: TopicRecord) -> None:
        clash = next(
            (
                other
                for other in self.topics.values()
                if (other.subject_id, other.parent_topic_id, other.name)
                == (record.subject_id, record.parent_topic_id, record.name)
            ),
            None,
        )
        if clash is not None:
            raise AssertionError(f"topic name {record.name!r} is already used under this parent")
        self.topics[record.id] = record

    def update_topic(self, record: TopicRecord) -> None:
        self._require(record.id in self.topics, f"topic {record.id}")
        self.topics[record.id] = record

    # -- topic relationships ------------------------------------------------

    def list_topic_relationships(
        self, curriculum_version_id: uuid.UUID
    ) -> tuple[TopicRelationshipRecord, ...]:
        topic_ids = {record.id for record in self.list_topics(curriculum_version_id)}
        return tuple(
            record for record in self.relationships.values() if record.source_topic_id in topic_ids
        )

    def add_topic_relationship(self, record: TopicRelationshipRecord) -> None:
        key = (record.source_topic_id, record.target_topic_id, record.relationship_type)
        if key in self.relationships:
            raise AssertionError(f"topic relationship {key} is already stored")
        self.relationships[key] = record

    # -- unit of work -------------------------------------------------------

    def flush(self) -> None:
        self.flush_calls += 1

    @staticmethod
    def _require(condition: bool, what: str) -> None:
        if not condition:
            raise AssertionError(f"{what} is not stored")
