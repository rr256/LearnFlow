"""SQLAlchemy implementation of the learning-resource repository port.

Serves RES-001 to RES-004. It maps rows to the application's plain records and
back, replaces a resource's topic links as one set, and reads the curriculum rows
that name what a resource covers.

It decides nothing. Which kinds of material may be catalogued, what counts as a
usable link, whether a resource belongs to the effective learner, and what a
learner may change are all settled by the use case
(docs/architecture/dependency-rules.md).

The session's transaction is owned by the caller. Nothing here commits.
"""

import uuid
from collections.abc import Mapping, Sequence

from sqlalchemy import ColumnElement, Select, delete, func, select
from sqlalchemy.orm import Session

from app.application.dto.resource import PRIMARY, ResourceFilters, ResourceRecord, ResourceTopic
from app.infrastructure.persistence.curriculum import Subject, Topic
from app.infrastructure.persistence.resources import Resource as ResourceRow
from app.infrastructure.persistence.resources import ResourceTopicLink


class SqlAlchemyResourceRepository:
    """Reads and writes a learner's learning resources through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one unit of work."""
        self._session = session

    def count_resources(self, *, learner_id: uuid.UUID, filters: ResourceFilters) -> int:
        """How many of this learner's resources match, ignoring any page window."""
        total = self._session.scalar(
            select(func.count())
            .select_from(ResourceRow)
            .where(*_filters(learner_id, filters))
            .where(*_topic_condition(filters))
        )
        return int(total or 0)

    def list_resources(
        self,
        *,
        learner_id: uuid.UUID,
        filters: ResourceFilters,
        limit: int,
        offset: int,
    ) -> tuple[ResourceRecord, ...]:
        """One page of the learner's resources, newest first."""
        rows = self._session.scalars(
            _ordered(
                select(ResourceRow)
                .where(*_filters(learner_id, filters))
                .where(*_topic_condition(filters))
            )
            .limit(limit)
            .offset(offset)
        ).all()
        return tuple(_record(row) for row in rows)

    def find_resource(self, resource_id: uuid.UUID) -> ResourceRecord | None:
        """The resource with this identifier, or None."""
        row = self._session.get(ResourceRow, resource_id)
        return None if row is None else _record(row)

    def add_resource(self, record: ResourceRecord) -> None:
        """Store a new resource."""
        self._session.add(
            ResourceRow(
                id=record.id,
                owner_learner_id=record.owner_learner_id,
                resource_type=record.resource_type,
                title=record.title,
                source_label=record.source_label,
                external_reference=record.external_reference,
                status=record.status,
            )
        )

    def update_resource(self, record: ResourceRecord) -> None:
        """Store a changed resource.

        Raises:
            LookupError: The resource is not stored. The use case has already
                established that it is, so reaching this means the row vanished
                between the read and the write.
        """
        row = self._session.get(ResourceRow, record.id)
        if row is None:
            raise LookupError(f"No learning resource is stored with identifier {record.id}.")
        row.resource_type = record.resource_type
        row.title = record.title
        row.source_label = record.source_label
        row.external_reference = record.external_reference
        row.status = record.status

    def delete_resource(self, resource_id: uuid.UUID) -> None:
        """Remove the resource row. A row that is not there is already gone.

        Only the row: the use case has already cleared what hangs off it, and the
        foreign keys are not cascades, so this fails loudly rather than quietly
        widening if a child was missed.
        """
        row = self._session.get(ResourceRow, resource_id)
        if row is not None:
            self._session.delete(row)

    def replace_topic_links(
        self, *, resource_id: uuid.UUID, topic_ids: Sequence[uuid.UUID]
    ) -> None:
        """Make these topics the resource's links, removing any others.

        A delete and an insert rather than a merge, which is what makes adding,
        removing, and reordering the same request and one transaction. The links
        are write-once rows with no state of their own, so nothing is lost by
        rewriting them -- unlike a plan item, whose status is the learner's own
        statement.
        """
        self._session.execute(
            delete(ResourceTopicLink).where(ResourceTopicLink.resource_id == resource_id)
        )
        # Flushed before the inserts so a replaced set cannot collide with the
        # composite primary key of the rows being removed in the same statement
        # batch.
        self._session.flush()
        for topic_id in topic_ids:
            self._session.add(
                ResourceTopicLink(
                    resource_id=resource_id,
                    topic_id=topic_id,
                    # The only role written. See `RESOURCE_TOPIC_ROLES`.
                    relationship_type=PRIMARY,
                )
            )

    def list_topic_links(
        self, resource_ids: Sequence[uuid.UUID]
    ) -> Mapping[uuid.UUID, tuple[uuid.UUID, ...]]:
        """The topic identifiers each resource names, keyed by resource."""
        if not resource_ids:
            return {}
        rows = self._session.execute(
            select(ResourceTopicLink.resource_id, ResourceTopicLink.topic_id)
            .where(ResourceTopicLink.resource_id.in_(resource_ids))
            # Ordered so a resource's topics read the same way on every request;
            # the composite key alone leaves the order to the database.
            .order_by(
                ResourceTopicLink.resource_id,
                ResourceTopicLink.created_at,
                ResourceTopicLink.topic_id,
            )
        ).all()

        links: dict[uuid.UUID, tuple[uuid.UUID, ...]] = {}
        for resource_id, topic_id in rows:
            links[resource_id] = (*links.get(resource_id, ()), topic_id)
        return links

    def list_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[ResourceTopic, ...]:
        """The topics named, in no particular order."""
        if not topic_ids:
            return ()
        rows = self._session.execute(
            select(Topic.id, Topic.code, Topic.name, Subject.id, Subject.name)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(Topic.id.in_(set(topic_ids)))
        ).all()
        return tuple(
            ResourceTopic(
                id=row[0], code=row[1], name=row[2], subject_id=row[3], subject_name=row[4]
            )
            for row in rows
        )


def _filters(learner_id: uuid.UUID, filters: ResourceFilters) -> tuple[ColumnElement[bool], ...]:
    """The conditions a listed resource must meet, other than its topic.

    No status is assumed. A caller that wants only what is in the catalogue asks
    for `registered`, and one that wants what has been put aside asks for
    `archived`, which is how PLN-002 and REV-001 treat their own statuses.
    """
    conditions: list[ColumnElement[bool]] = [ResourceRow.owner_learner_id == learner_id]
    if filters.resource_type is not None:
        conditions.append(ResourceRow.resource_type == filters.resource_type)
    if filters.status is not None:
        conditions.append(ResourceRow.status == filters.status)
    return tuple(conditions)


def _topic_condition(filters: ResourceFilters) -> tuple[ColumnElement[bool], ...]:
    """Restrict to resources linked to one topic, when one was asked for.

    Expressed as an `EXISTS` rather than a join, so a resource covering a topic
    appears once however many links it holds -- a join would repeat it and make
    the page window count the same resource twice.
    """
    if filters.topic_id is None:
        return ()
    return (
        select(ResourceTopicLink.resource_id)
        .where(
            ResourceTopicLink.resource_id == ResourceRow.id,
            ResourceTopicLink.topic_id == filters.topic_id,
        )
        .exists(),
    )


def _ordered(statement: Select[tuple[ResourceRow]]) -> Select[tuple[ResourceRow]]:
    """Newest first, then by identifier.

    The order every learner-owned collection uses. The identifier breaks a tie
    two resources registered in the same instant would otherwise leave to the
    database, which would let one page repeat or omit a record.
    """
    return statement.order_by(ResourceRow.created_at.desc(), ResourceRow.id)


def _record(row: ResourceRow) -> ResourceRecord:
    """Map a stored row onto the application's plain record."""
    return ResourceRecord(
        id=row.id,
        owner_learner_id=row.owner_learner_id,
        resource_type=row.resource_type,
        title=row.title,
        source_label=row.source_label,
        external_reference=row.external_reference,
        status=row.status,
    )
