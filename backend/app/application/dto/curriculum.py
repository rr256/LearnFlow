"""Output structures for reading the curriculum.

These are what a learner browses: a learning program, the curriculum version
that is currently active for it, and that version's subjects, topics, and
subtopics with the relationships between them.

They are framework-independent by design. The API schemas that serialise them
are a separate representation, so a change to the HTTP contract does not reach
back into the use case, and a change here does not silently alter the contract.

Curriculum data is reference data: nothing here is learner-owned, and none of it
carries a `learner_id`.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CurriculumVersionReference:
    """A curriculum version, named well enough to fetch its tree.

    `source_reference` is the official or curator reference the version was
    transcribed from, and is nullable because a version need not have one.
    `published_at` is set when a version becomes active.
    """

    id: uuid.UUID
    learning_program_id: uuid.UUID
    version_label: str
    status: str
    source_reference: str | None
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class LearningProgramSummary:
    """A learning program and the curriculum version currently active for it.

    `active_curriculum_version` is None while a program has only draft or
    retired versions, which is a real state rather than an error: a program can
    be stored before its curriculum is published.
    """

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    active_curriculum_version: CurriculumVersionReference | None


@dataclass(frozen=True, slots=True)
class LearningProgramPage:
    """One requested window over the stored learning programs.

    `total` counts every stored program, not the window, so a client can tell a
    complete list from a truncated one.
    """

    programs: tuple[LearningProgramSummary, ...]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class TopicNode:
    """A topic, with any subtopics nested beneath it.

    `is_trackable` says whether learner progress can be recorded directly
    against this topic. A topic that only groups subtopics is not trackable.
    """

    id: uuid.UUID
    code: str | None
    name: str
    description: str | None
    position: int
    is_trackable: bool
    subtopics: tuple[TopicNode, ...]


@dataclass(frozen=True, slots=True)
class SubjectNode:
    """A subject and its root topics, in recommended order."""

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    position: int
    topics: tuple[TopicNode, ...]


@dataclass(frozen=True, slots=True)
class TopicRelationshipEdge:
    """A prerequisite or sequencing edge between two topics of this version.

    Reported as a flat list beside the tree rather than inlined on each topic:
    an edge is a relation between two topics, and nesting it under one of them
    would make the tree assert which end owns it.
    """

    source_topic_id: uuid.UUID
    target_topic_id: uuid.UUID
    relationship_type: str


@dataclass(frozen=True, slots=True)
class CurriculumTree:
    """One curriculum version's full hierarchy."""

    curriculum_version: CurriculumVersionReference
    subjects: tuple[SubjectNode, ...]
    topic_relationships: tuple[TopicRelationshipEdge, ...]
