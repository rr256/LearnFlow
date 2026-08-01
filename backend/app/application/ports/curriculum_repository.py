"""The persistence port the curriculum read use case works through.

Reading the curriculum needs none of the write primitives
`CurriculumSeedRepository` offers, and a port that could also write is one a
reviewer has to read twice before trusting a read path. This port is therefore
separate and read-only.

It reuses the record types the seed port already declares rather than defining a
second set describing the same rows; `study_goal_repository` reads the
examination schedule records the same way. The records are plain application
values, so nothing above this port ever sees an ORM row.

Ordering is the use case's business, not the store's, with one exception noted
on `list_learning_programs`: a page cannot be ordered after it has been sliced.
"""

import uuid
from collections.abc import Sequence
from typing import Protocol

from app.application.ports.curriculum_seed_repository import (
    CurriculumVersionRecord,
    LearningProgramRecord,
    SubjectRecord,
    TopicRecord,
    TopicRelationshipRecord,
)


class CurriculumRepository(Protocol):
    """Reads the curriculum hierarchy a learner browses."""

    def count_learning_programs(self) -> int:
        """How many learning programs are stored, ignoring any page window."""
        ...

    def list_learning_programs(
        self, *, limit: int, offset: int
    ) -> tuple[LearningProgramRecord, ...]:
        """One page of learning programs, ordered by `code`.

        The order is fixed here rather than in the use case because a page is
        chosen by the store: slicing first and sorting afterwards would return a
        different set of rows for the same offset.
        """
        ...

    def find_learning_program(self, learning_program_id: uuid.UUID) -> LearningProgramRecord | None:
        """The program with this identifier, or None."""
        ...

    def list_active_curriculum_versions(
        self, learning_program_ids: Sequence[uuid.UUID]
    ) -> tuple[CurriculumVersionRecord, ...]:
        """The active curriculum version of each program named, where one exists.

        Every identifier is asked for at once so listing programs stays one
        query rather than one per program. A program with no active version is
        absent from the result; at most one can be present per program, because
        a partial unique index enforces it (ADR-011).
        """
        ...

    def find_curriculum_version(
        self, curriculum_version_id: uuid.UUID
    ) -> CurriculumVersionRecord | None:
        """The curriculum version with this identifier, or None."""
        ...

    def list_subjects(self, curriculum_version_id: uuid.UUID) -> tuple[SubjectRecord, ...]:
        """Every subject of this version."""
        ...

    def list_topics(self, curriculum_version_id: uuid.UUID) -> tuple[TopicRecord, ...]:
        """Every topic under every subject of this version, at any depth."""
        ...

    def list_topic_relationships(
        self, curriculum_version_id: uuid.UUID
    ) -> tuple[TopicRelationshipRecord, ...]:
        """Every relationship whose source topic belongs to this version."""
        ...
