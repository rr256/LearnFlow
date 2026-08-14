"""The persistence port the revision endpoints work through.

It reads and writes the learner's revision records, and reads the two things a
revision has to be explained by: the topic it names, and the completed work it
came from. Reading all of them through one port keeps a request to one unit of
work, for the reason `topic_progress_repository` records.

Ordering of a page is fixed here, for the reason `curriculum_repository` records:
a page cannot be ordered after it has been sliced. Revisions are ordered by the
day they fall due, earliest first, because that is the order a learner works
through them.
"""

import uuid
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Protocol

from app.application.dto.revision import (
    RevisionFilters,
    RevisionRecord,
    RevisionTopic,
)


class RevisionRepository(Protocol):
    """Reads and writes a learner's revisions."""

    def count_revisions(self, *, learner_id: uuid.UUID, filters: RevisionFilters) -> int:
        """How many of this learner's revisions match, for the pagination block."""
        ...

    def list_revisions(
        self,
        *,
        learner_id: uuid.UUID,
        filters: RevisionFilters,
        limit: int,
        offset: int,
    ) -> tuple[RevisionRecord, ...]:
        """One page of the learner's revisions, earliest due date first."""
        ...

    def list_all_revisions(self, learner_id: uuid.UUID) -> tuple[RevisionRecord, ...]:
        """Every revision this learner has, unpaged.

        Unpaged because scheduling asks a membership question over the whole set
        — which topics already have a revision waiting — and a window over it
        would let a run create a duplicate for a topic just outside the page.
        """
        ...

    def find_revision(self, revision_id: uuid.UUID) -> RevisionRecord | None:
        """The revision with this identifier, or None.

        Ownership is a rule, so the use case decides it. This returns the record
        whoever owns it, and the caller compares.
        """
        ...

    def add_revision(self, record: RevisionRecord) -> None:
        """Store a new revision. The caller owns the transaction."""
        ...

    def update_revision(self, record: RevisionRecord) -> None:
        """Store a changed revision. The caller owns the transaction."""
        ...

    def list_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[RevisionTopic, ...]:
        """The topics named, in no particular order.

        Every identifier is asked for at once so listing a page stays one query
        rather than one per record. An identifier naming no stored topic is
        absent from the result, which the use case reports as a revision whose
        topic is no longer stored rather than as a failure.
        """
        ...

    def list_recorded_stages(
        self, *, learner_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, str]:
        """The learning stage this learner recorded for each topic named.

        Keyed by topic, and a topic with no record is simply absent — nothing
        creates a row on a learner's behalf (ADR-017), so an absent key means
        *no stage recorded* rather than a stage of some default value.

        Scoped by topic rather than by curriculum version, unlike the planner's
        equivalent: a revision names a topic and belongs to no goal, so a version
        would be a parameter this use case has no reason to know.
        """
        ...

    def list_completed_topic_work(
        self, learner_id: uuid.UUID
    ) -> tuple[tuple[uuid.UUID, uuid.UUID, date], ...]:
        """Each topic the learner has completed planned work on, once.

        Returns `(topic_id, plan_item_id, completed_on)` for the **earliest**
        completion of each topic across every one of the learner's plans,
        superseded ones included: superseding a plan does not un-complete the
        work done under it, which is ADR-022's rule and the one adaptation
        applies.

        The earliest rather than the latest, so a learner who completes the same
        topic on two plans is offered revision from when they first finished it
        rather than having the date pushed back by a repeat.
        """
        ...
