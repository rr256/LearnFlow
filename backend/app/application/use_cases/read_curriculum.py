"""Read the curated curriculum a learner browses.

This is the read side of the curriculum area, serving CUR-001 to CUR-003 in
docs/api/endpoints.md. It writes nothing.

Two rules live here rather than in the store or the route.

**Display order is a curriculum decision.** Subjects and topics carry a
`position` recording the order the syllabus teaches them in, and this use case
applies it, so the order a learner sees does not depend on how a repository
happened to write its query.

**A tree is assembled, not stored.** The database holds topics as a flat table
with a self-referencing parent, because that is what a hierarchy of unknown
depth needs to be stored as. Turning that back into nested subtopics is a
decision about what a client is shown, so it belongs above the repository.
"""

import uuid
from collections import defaultdict
from collections.abc import Sequence

from app.application.dto.curriculum import (
    CurriculumTree,
    CurriculumVersionReference,
    LearningProgramPage,
    LearningProgramSummary,
    SubjectNode,
    TopicNode,
    TopicRelationshipEdge,
)
from app.application.ports.curriculum_repository import CurriculumRepository
from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
    SubjectRecord,
    TopicRecord,
)


class CurriculumReadError(Exception):
    """The curriculum could not be read as asked."""


class LearningProgramNotFoundError(CurriculumReadError):
    """No learning program is stored with the requested identifier."""


class CurriculumVersionNotFoundError(CurriculumReadError):
    """No curriculum version is stored with the requested identifier."""


class ReadCurriculum:
    """Serves the curriculum hierarchy through a `CurriculumRepository`."""

    def __init__(self, repository: CurriculumRepository) -> None:
        """Wire the use case.

        Args:
            repository: Where the curriculum is read from.
        """
        self._repository = repository

    def list_learning_programs(self, *, limit: int, offset: int) -> LearningProgramPage:
        """One page of learning programs, each with its active curriculum version.

        Args:
            limit: How many programs to return. The caller validates the bound;
                this reports back what it was given so a client can confirm the
                window it received.
            offset: How many programs to skip.
        """
        programs = self._repository.list_learning_programs(limit=limit, offset=offset)
        active = self._active_versions_by_program([program.id for program in programs])
        return LearningProgramPage(
            programs=tuple(
                _program_summary(program, active.get(program.id)) for program in programs
            ),
            total=self._repository.count_learning_programs(),
            limit=limit,
            offset=offset,
        )

    def read_learning_program(self, learning_program_id: uuid.UUID) -> LearningProgramSummary:
        """One learning program and the curriculum version active for it.

        Raises:
            LearningProgramNotFoundError: No such program is stored.
        """
        program = self._repository.find_learning_program(learning_program_id)
        if program is None:
            raise LearningProgramNotFoundError(
                f"No learning program is stored with identifier {learning_program_id}."
            )
        active = self._active_versions_by_program([program.id])
        return _program_summary(program, active.get(program.id))

    def read_curriculum_tree(self, curriculum_version_id: uuid.UUID) -> CurriculumTree:
        """One curriculum version's subjects, topics, subtopics, and relationships.

        A version with no subjects yet returns an empty tree rather than an
        error: an unpopulated draft version is a real state, not a failure.

        Raises:
            CurriculumVersionNotFoundError: No such version is stored.
        """
        version = self._repository.find_curriculum_version(curriculum_version_id)
        if version is None:
            raise CurriculumVersionNotFoundError(
                f"No curriculum version is stored with identifier {curriculum_version_id}."
            )

        subjects = self._repository.list_subjects(curriculum_version_id)
        topics = self._repository.list_topics(curriculum_version_id)
        relationships = self._repository.list_topic_relationships(curriculum_version_id)

        return CurriculumTree(
            curriculum_version=_version_reference(version),
            subjects=_subject_nodes(subjects, topics),
            topic_relationships=tuple(
                TopicRelationshipEdge(
                    source_topic_id=relationship.source_topic_id,
                    target_topic_id=relationship.target_topic_id,
                    relationship_type=relationship.relationship_type,
                )
                for relationship in relationships
            ),
        )

    def _active_versions_by_program(
        self, learning_program_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, CurriculumVersionRecord]:
        if not learning_program_ids:
            return {}
        versions = self._repository.list_active_curriculum_versions(learning_program_ids)
        return {version.learning_program_id: version for version in versions}


def _program_summary(
    program: LearningProgramRecord, active_version: CurriculumVersionRecord | None
) -> LearningProgramSummary:
    return LearningProgramSummary(
        id=program.id,
        code=program.code,
        name=program.name,
        description=program.description,
        active_curriculum_version=(
            None if active_version is None else _version_reference(active_version)
        ),
    )


def _version_reference(version: CurriculumVersionRecord) -> CurriculumVersionReference:
    return CurriculumVersionReference(
        id=version.id,
        learning_program_id=version.learning_program_id,
        version_label=version.version_label,
        status=version.status,
        source_reference=version.source_reference,
        published_at=version.published_at,
    )


def _subject_nodes(
    subjects: Sequence[SubjectRecord], topics: Sequence[TopicRecord]
) -> tuple[SubjectNode, ...]:
    """Nest the flat topic rows under their subjects, in recommended order.

    A topic whose parent is not among these rows is treated as a root of its own
    subject rather than dropped, so a topic can never disappear because its
    parent belongs to another curriculum version.

    A topic whose parent chain never reaches a root -- two topics naming each
    other as parent, say -- is not reachable and so is omitted. The seed cannot
    produce that shape: it writes a parent before its children, so a cycle would
    need a hand-edited database.
    """
    stored = {topic.id for topic in topics}
    roots: dict[uuid.UUID, list[TopicRecord]] = defaultdict(list)
    children: dict[uuid.UUID, list[TopicRecord]] = defaultdict(list)

    for topic in topics:
        parent_id = topic.parent_topic_id
        if parent_id is None or parent_id not in stored:
            roots[topic.subject_id].append(topic)
        else:
            children[parent_id].append(topic)

    return tuple(
        SubjectNode(
            id=subject.id,
            code=subject.code,
            name=subject.name,
            description=subject.description,
            position=subject.position,
            topics=_topic_nodes(roots[subject.id], children),
        )
        for subject in sorted(subjects, key=_by_position)
    )


def _topic_nodes(
    topics: Sequence[TopicRecord], children: dict[uuid.UUID, list[TopicRecord]]
) -> tuple[TopicNode, ...]:
    return tuple(
        TopicNode(
            id=topic.id,
            code=topic.code,
            name=topic.name,
            description=topic.description,
            position=topic.position,
            is_trackable=topic.is_trackable,
            subtopics=_topic_nodes(children[topic.id], children),
        )
        for topic in sorted(topics, key=_by_position)
    )


def _by_position(record: SubjectRecord | TopicRecord) -> int:
    return record.position
