"""An in-memory stand-in for the learning-resource repository port.

Resources are held in registration order and returned newest first, matching the
order the port fixes and the SQLAlchemy adapter applies — so a use case relying
on the store to sort fails here rather than passing by accident.

The controlled values are asserted on write, mirroring the database `CHECK`s: a
fake accepting a type or a status PostgreSQL would refuse would let a use-case
test pass on a shape the real database cannot store. The "names a location"
constraint is asserted too, because it is the one invariant a resource carries
that no other record does.

The curriculum topics are supplied as a fixture rather than derived, because what
this fake stands in for is the *query*, and the rule being tested is what the use
case does with its answer.
"""

import uuid
from collections.abc import Mapping, Sequence

from app.application.dto.resource import (
    RESOURCE_STATUSES,
    RESOURCE_TYPES,
    ResourceFilters,
    ResourceRecord,
    ResourceTopic,
)


class FakeResourceRepository:
    """Stores resources and their topic links in lists, over fixed curriculum data."""

    def __init__(
        self,
        *,
        resources: Sequence[ResourceRecord] = (),
        topics: Sequence[ResourceTopic] = (),
        links: Mapping[uuid.UUID, Sequence[uuid.UUID]] | None = None,
    ) -> None:
        """Start from stored resources, their links, and the topics they name."""
        self.resources = list(resources)
        self.topics = list(topics)
        self.links: dict[uuid.UUID, tuple[uuid.UUID, ...]] = {
            resource_id: tuple(topic_ids) for resource_id, topic_ids in (links or {}).items()
        }

    def count_resources(self, *, learner_id: uuid.UUID, filters: ResourceFilters) -> int:
        return len(self._matching(learner_id, filters))

    def list_resources(
        self,
        *,
        learner_id: uuid.UUID,
        filters: ResourceFilters,
        limit: int,
        offset: int,
    ) -> tuple[ResourceRecord, ...]:
        return tuple(self._matching(learner_id, filters)[offset : offset + limit])

    def find_resource(self, resource_id: uuid.UUID) -> ResourceRecord | None:
        return next((record for record in self.resources if record.id == resource_id), None)

    def add_resource(self, record: ResourceRecord) -> None:
        self._require_storable(record)
        if any(stored.id == record.id for stored in self.resources):
            raise AssertionError(f"Resource {record.id} is already stored.")
        self.resources.append(record)

    def update_resource(self, record: ResourceRecord) -> None:
        self._require_storable(record)
        for index, stored in enumerate(self.resources):
            if stored.id == record.id:
                self.resources[index] = record
                return
        raise LookupError(f"No learning resource is stored with identifier {record.id}.")

    def replace_topic_links(
        self, *, resource_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]
    ) -> None:
        if topic_ids:
            self.links[resource_id] = tuple(topic_ids)
        else:
            self.links.pop(resource_id, None)

    def list_topic_links(
        self, resource_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, tuple[uuid.UUID, ...]]:
        wanted = set(resource_ids)
        return {
            resource_id: topic_ids
            for resource_id, topic_ids in self.links.items()
            if resource_id in wanted
        }

    def list_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[ResourceTopic, ...]:
        wanted = set(topic_ids)
        return tuple(topic for topic in self.topics if topic.id in wanted)

    def _matching(self, learner_id: uuid.UUID, filters: ResourceFilters) -> list[ResourceRecord]:
        matched = [record for record in self.resources if record.owner_learner_id == learner_id]
        if filters.resource_type is not None:
            matched = [
                record for record in matched if record.resource_type == filters.resource_type
            ]
        if filters.status is not None:
            matched = [record for record in matched if record.status == filters.status]
        if filters.topic_id is not None:
            matched = [
                record for record in matched if filters.topic_id in self.links.get(record.id, ())
            ]
        # Newest first, as the port fixes. Registration order stands in for
        # `created_at`, which the record does not carry.
        return list(reversed(matched))

    @staticmethod
    def _require_storable(record: ResourceRecord) -> None:
        """Refuse what the database's CHECK constraints would refuse."""
        if record.resource_type not in RESOURCE_TYPES:
            raise AssertionError(f"'{record.resource_type}' is not a stored resource type.")
        if record.status not in RESOURCE_STATUSES:
            raise AssertionError(f"'{record.status}' is not a stored resource status.")
        if record.source_label is None and record.external_reference is None:
            raise AssertionError("A stored resource must name a location.")


def resource_topic(
    name: str = "CPU scheduling",
    *,
    subject_name: str = "Operating Systems",
    topic_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
) -> ResourceTopic:
    """A curriculum topic a resource can be linked to."""
    return ResourceTopic(
        id=topic_id or uuid.uuid4(),
        code=None,
        name=name,
        subject_id=subject_id or uuid.uuid4(),
        subject_name=subject_name,
    )
