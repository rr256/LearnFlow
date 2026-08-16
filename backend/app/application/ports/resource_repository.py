"""The persistence port the learning-resource endpoints work through.

It reads and writes the learner's resources, their topic links, and the
curriculum rows needed to name what a resource covers. Reading all of them
through one port keeps a request to one unit of work, for the reason
`topic_progress_repository` records.

Ordering of a page is fixed here, for the reason `curriculum_repository`
records: a page cannot be ordered after it has been sliced. Resources are
ordered newest first, which is the order every other learner-owned collection
uses.
"""

import uuid
from collections.abc import Mapping, Sequence
from typing import Protocol

from app.application.dto.resource import ResourceFilters, ResourceRecord, ResourceTopic


class ResourceRepository(Protocol):
    """Reads and writes a learner's learning resources."""

    def count_resources(self, *, learner_id: uuid.UUID, filters: ResourceFilters) -> int:
        """How many of this learner's resources match, for the pagination block."""
        ...

    def list_resources(
        self,
        *,
        learner_id: uuid.UUID,
        filters: ResourceFilters,
        limit: int,
        offset: int,
    ) -> tuple[ResourceRecord, ...]:
        """One page of the learner's resources, newest first."""
        ...

    def find_resource(self, resource_id: uuid.UUID) -> ResourceRecord | None:
        """The resource with this identifier, or None.

        Ownership is a rule, so the use case decides it. This returns the record
        whoever owns it, and the caller compares.
        """
        ...

    def add_resource(self, record: ResourceRecord) -> None:
        """Store a new resource. The caller owns the transaction."""
        ...

    def update_resource(self, record: ResourceRecord) -> None:
        """Store a changed resource. The caller owns the transaction."""
        ...

    def replace_topic_links(
        self, *, resource_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]
    ) -> None:
        """Make these topics the resource's links, removing any others.

        A replacement rather than a merge, which is GOAL-005's rule for a week
        applied to a link set: adding a topic, removing one, and changing the set
        are the same request, and each is one transaction, so an edit spanning
        three links cannot leave one saved and two lost.
        """
        ...

    def list_topic_links(
        self, resource_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, tuple[uuid.UUID, ...]]:
        """The topic identifiers each resource names, keyed by resource.

        Every resource on a page is asked for at once, so rendering a page stays
        one query rather than one per row. A resource with no links is absent
        from the mapping rather than present with an empty tuple.
        """
        ...

    def list_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[ResourceTopic, ...]:
        """The topics named, in no particular order.

        Every identifier is asked for at once for the reason above. An identifier
        naming no stored topic is absent from the result, which is how the use
        case refuses a request that names one and how it reports a link whose
        topic has since gone.
        """
        ...
