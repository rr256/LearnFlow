"""The persistence port the topic-progress endpoints work through.

It reads two kinds of row and writes one. The learner-owned progress records are
its own; the topic rows are curriculum reference data, read here only to name a
record and to report whether the topic accepts progress at all.

Reading topics through this port rather than through `CurriculumRepository` keeps
one request to one unit of work: PRG-002 needs the topic behind every record it
returns, and asking a second repository would mean a second session or one shared
between them. The records are reused rather than redeclared, as elsewhere in this
package.

Ordering of a page is fixed here, for the reason `curriculum_repository` records:
a page cannot be ordered after it has been sliced.
"""

import uuid
from collections.abc import Sequence
from typing import Protocol

from app.application.dto.topic_progress import TopicProgressRecord, TopicProgressTopic


class TopicProgressRepository(Protocol):
    """Reads and writes what a learner has recorded about topics."""

    def find_topic(self, topic_id: uuid.UUID) -> TopicProgressTopic | None:
        """The topic with this identifier, or None.

        Whether a topic that only groups subtopics may hold progress is a rule,
        so the use case decides it. This reports `is_trackable` rather than
        filtering on it.
        """
        ...

    def list_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[TopicProgressTopic, ...]:
        """The topics named, in no particular order.

        Every identifier is asked for at once so listing a page of progress stays
        one query rather than one per record. An identifier naming no stored
        topic is absent from the result.
        """
        ...

    def count_topic_progress(
        self, *, learner_id: uuid.UUID, curriculum_version_id: uuid.UUID | None
    ) -> int:
        """How many of this learner's records match, ignoring any page window."""
        ...

    def list_topic_progress(
        self,
        *,
        learner_id: uuid.UUID,
        curriculum_version_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[TopicProgressRecord, ...]:
        """One page of the learner's records, newest first.

        `curriculum_version_id` restricts the page to topics belonging to that
        version. A version that is not stored matches nothing, which is an empty
        page rather than a failure.
        """
        ...

    def find_topic_progress(
        self, *, learner_id: uuid.UUID, topic_id: uuid.UUID
    ) -> TopicProgressRecord | None:
        """This learner's record for this topic, or None.

        None means the learner has recorded nothing against it, which reads as
        the neutral starting stage rather than as a missing record.
        """
        ...

    def add_topic_progress(self, record: TopicProgressRecord) -> None:
        """Store a new progress record."""
        ...

    def update_topic_progress(self, record: TopicProgressRecord) -> None:
        """Overwrite the stored record identified by ``record.id``."""
        ...
