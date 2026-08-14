"""An in-memory stand-in for the revision repository port.

Revisions are held in insertion order and returned sorted by due date, matching
the order the port fixes and the SQLAlchemy adapter applies — so a use case
relying on the store to sort fails here rather than passing by accident.

The controlled values are asserted on write, mirroring the database `CHECK`s: a
fake accepting a status or a trigger PostgreSQL would refuse would let a use-case
test pass on a shape the real database cannot store.

The completed study work and the recorded stages are supplied as fixtures rather
than derived, because what this fake stands in for is the *query*, and the rule
being tested is what the use case does with its answer.
"""

import uuid
from collections.abc import Mapping, Sequence
from datetime import date

from app.application.dto.revision import (
    REVISION_STATUSES,
    REVISION_TRIGGERS,
    SETTLED_REVISION_STATUSES,
    RevisionFilters,
    RevisionRecord,
    RevisionTopic,
)


class FakeRevisionRepository:
    """Stores revisions in a list, over fixed curriculum and planning fixtures."""

    def __init__(
        self,
        *,
        revisions: Sequence[RevisionRecord] = (),
        topics: Sequence[RevisionTopic] = (),
        completed_work: Sequence[tuple[uuid.UUID, uuid.UUID, date]] = (),
        stages: Mapping[uuid.UUID, str] | None = None,
    ) -> None:
        """Start from stored revisions and the reference data they describe."""
        self.revisions = list(revisions)
        self.topics = list(topics)
        self.completed_work = list(completed_work)
        self.stages = dict(stages or {})

    def count_revisions(self, *, learner_id: uuid.UUID, filters: RevisionFilters) -> int:
        return len(self._matching(learner_id, filters))

    def list_revisions(
        self,
        *,
        learner_id: uuid.UUID,
        filters: RevisionFilters,
        limit: int,
        offset: int,
    ) -> tuple[RevisionRecord, ...]:
        return tuple(self._matching(learner_id, filters)[offset : offset + limit])

    def list_all_revisions(self, learner_id: uuid.UUID) -> tuple[RevisionRecord, ...]:
        return tuple(
            self._ordered(record for record in self.revisions if record.learner_id == learner_id)
        )

    def find_revision(self, revision_id: uuid.UUID) -> RevisionRecord | None:
        return next((record for record in self.revisions if record.id == revision_id), None)

    def add_revision(self, record: RevisionRecord) -> None:
        self._require_known(record)
        if any(stored.id == record.id for stored in self.revisions):
            raise AssertionError(f"Revision {record.id} is already stored.")
        self.revisions.append(record)

    def update_revision(self, record: RevisionRecord) -> None:
        self._require_known(record)
        for index, stored in enumerate(self.revisions):
            if stored.id == record.id:
                self.revisions[index] = record
                return
        raise LookupError(f"No revision is stored with identifier {record.id}.")

    def list_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[RevisionTopic, ...]:
        wanted = set(topic_ids)
        return tuple(topic for topic in self.topics if topic.id in wanted)

    def list_recorded_stages(
        self, *, learner_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, str]:
        wanted = set(topic_ids)
        return {topic_id: stage for topic_id, stage in self.stages.items() if topic_id in wanted}

    def list_completed_topic_work(
        self, learner_id: uuid.UUID
    ) -> tuple[tuple[uuid.UUID, uuid.UUID, date], ...]:
        return tuple(self.completed_work)

    def _matching(self, learner_id: uuid.UUID, filters: RevisionFilters) -> list[RevisionRecord]:
        matched = [record for record in self.revisions if record.learner_id == learner_id]
        if filters.status is not None:
            matched = [record for record in matched if record.status == filters.status]
        if filters.due_only:
            matched = [
                record for record in matched if record.status not in SETTLED_REVISION_STATUSES
            ]
        return self._ordered(matched)

    @staticmethod
    def _ordered(records) -> list[RevisionRecord]:
        """Earliest due date first, then by identifier, as the port fixes."""
        return sorted(records, key=lambda record: (record.due_on, record.id))

    @staticmethod
    def _require_known(record: RevisionRecord) -> None:
        """Refuse what the database's CHECK constraints would refuse."""
        if record.status not in REVISION_STATUSES:
            raise AssertionError(f"'{record.status}' is not a stored revision status.")
        if record.trigger_type not in REVISION_TRIGGERS:
            raise AssertionError(f"'{record.trigger_type}' is not a stored revision trigger.")
