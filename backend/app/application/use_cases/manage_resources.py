"""Registering a learner's study material, finding it, and keeping it current.

Serves RES-001 to RES-004, which begin
[FR-007](../../../docs/requirements/functional.md#fr-007-learning-resource-organization)
and supply the resource half of
[FR-006](../../../docs/requirements/functional.md#fr-006-revision-guidance)'s
second criterion.

**A resource is a record of where material is, never the material.** Nothing here
uploads, stores, downloads, extracts, or indexes a file: `storage_key`,
`metadata`, and `resource_ingestions` are all absent, and they arrive with the
ingestion change that has somewhere to put a file. What this stores is what
FR-007's third criterion asks for — a title, a type, where the material is, and
the curriculum areas it covers.

**Nothing about the learner's own machine is stored.** `external_reference`
accepts an `http` or `https` address and nothing else, so no absolute filesystem
path is written or returned — the rule
docs/api/endpoints.md#resource-and-ingestion-endpoints states for every resource
endpoint. Material that lives offline is carried by `source_label`, in the
learner's own words.

**Nothing is deleted.** A resource the learner is finished with is `archived`,
and archiving is reversible, which is the position ADR-022 took for a superseded
plan and ADR-012 for a seeded row.

**Nothing is recommended, ranked, scored, or counted.** A topic's resources are
the ones the learner linked to it, in the order they registered them. No resource
is suggested for a topic, promoted above another, or counted on any screen.

**Nothing else moves.** Registering, changing, or archiving a resource writes no
learning stage, no plan, no plan item, and no revision — a resource says where
material is, never that a topic is understood or that work happened.
"""

import uuid
from collections.abc import Sequence
from urllib.parse import urlsplit

from app.application.dto.resource import (
    MAX_TOPIC_LINKS,
    REGISTERED,
    RESOURCE_STATUSES,
    RESOURCE_TYPES,
    NewResource,
    ResourceChanges,
    ResourceDetail,
    ResourceFilters,
    ResourcePage,
    ResourceRecord,
    ResourceTopic,
)
from app.application.ports.learner_repository import LearnerRecord, LearnerRepository
from app.application.ports.resource_repository import ResourceRepository
from app.application.use_cases.local_learner import resolve_local_learner

REFERENCE_SCHEMES: tuple[str, ...] = ("http", "https")
"""The address schemes `external_reference` accepts.

Deliberately narrow. A `file:` address, a bare Windows path, or any other scheme
would put a location on the learner's own machine into the database and back out
over the API, which docs/api/endpoints.md forbids of every resource endpoint.
Material that is not on the web is described by `source_label` instead.
"""


class ResourceManagementError(Exception):
    """Base class for the refusals this use case makes."""


class LearnerNotSetUpError(ResourceManagementError):
    """No learner is stored, so no resource can be owned."""


class ResourceNotFoundError(ResourceManagementError):
    """No such resource is stored, or it belongs to another learner."""


class UnknownResourceTypeError(ResourceManagementError):
    """A kind of material this build does not catalogue."""


class UnknownResourceStatusError(ResourceManagementError):
    """A status a learner may not ask for.

    Raised for a value outside `RESOURCE_STATUSES`, which includes the three
    ingestion states: the schema documents them, but nothing extracts or indexes
    a resource, so asking for one would store a state nothing can leave.
    """


class MissingResourceTitleError(ResourceManagementError):
    """A resource with no title, which nothing could find again."""


class MissingResourceLocationError(ResourceManagementError):
    """A resource that says neither where it is nor what it is called.

    At least one of `source_label` and `external_reference` is required. It is
    the approved "at least one of `storage_key` or `external_reference`"
    constraint, read for a catalogue that stores no files: a record that cannot
    say where its material is is a title and nothing else.
    """


class UnsupportedReferenceSchemeError(ResourceManagementError):
    """A link that is not an `http` or `https` address."""


class UnknownTopicError(ResourceManagementError):
    """A topic identifier naming nothing stored."""


class DuplicateTopicLinkError(ResourceManagementError):
    """The same topic named more than once in one request."""


class TooManyTopicLinksError(ResourceManagementError):
    """More topics named than one request may link."""


class EmptyResourceUpdateError(ResourceManagementError):
    """An update naming no field to change."""


class ManageResources:
    """Registers, reads, and changes a learner's learning resources.

    One use case serves all four endpoints, so the rule deciding whether a
    resource belongs to the effective learner stays in one place — the reason
    `ManageRevisions` serves the revision endpoints together.
    """

    def __init__(self, *, learners: LearnerRepository, resources: ResourceRepository) -> None:
        """Bind the use case to its ports."""
        self._learners = learners
        self._resources = resources

    def register(self, new_resource: NewResource) -> ResourceDetail:
        """Record where one piece of study material is, and what it covers.

        The caller owns the transaction: this writes through the repository but
        never commits.

        **A resource may name any stored topic**, including one that only groups
        subtopics. That is deliberately unlike PRG-004, which refuses a stage on
        a grouping topic: a stage is a claim about *understanding* a unit of
        work, and a heading is not one, while a textbook covering the whole of
        Operating Systems is describing exactly that heading.

        Raises:
            LearnerNotSetUpError: No learner exists to own the resource.
            AmbiguousLocalLearnerError: More than one learner is stored.
            UnknownResourceTypeError: The type is not one this build catalogues.
            MissingResourceTitleError: The title is empty.
            MissingResourceLocationError: Neither a label nor a link was given.
            UnsupportedReferenceSchemeError: The link is not `http` or `https`.
            UnknownTopicError: A topic identifier names nothing stored.
            DuplicateTopicLinkError: A topic was named more than once.
            TooManyTopicLinksError: More topics than one request may link.
        """
        learner = self._require_learner()

        title = _require_title(new_resource.title)
        _require_known_type(new_resource.resource_type)
        source_label = _blank_to_none(new_resource.source_label)
        external_reference = _validated_reference(new_resource.external_reference)
        _require_a_location(source_label=source_label, external_reference=external_reference)
        topic_ids = self._validated_topics(new_resource.topic_ids)

        record = ResourceRecord(
            id=uuid.uuid4(),
            owner_learner_id=learner.id,
            resource_type=new_resource.resource_type,
            title=title,
            source_label=source_label,
            external_reference=external_reference,
            # Every resource is written registered. Archiving is a later
            # statement the learner makes, never a state anything starts in.
            status=REGISTERED,
        )
        self._resources.add_resource(record)
        self._resources.replace_topic_links(resource_id=record.id, topic_ids=topic_ids)
        return self._describe([record])[0]

    def list_resources(self, *, filters: ResourceFilters, limit: int, offset: int) -> ResourcePage:
        """One page of the learner's resources, newest first.

        An installation where setup has not run has no learner and therefore no
        resources, which is an empty page rather than a failure. A `topic_id`
        matching nothing is an empty page too — a filter that matches nothing is
        an empty result, not a missing record — while an unknown *type* or
        *status* is refused, because a caller asking for one has misread the
        contract and an empty page would let it keep doing so.

        Raises:
            UnknownResourceTypeError: The type filter names an unknown kind.
            UnknownResourceStatusError: The status filter names an unknown state.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        if filters.resource_type is not None:
            _require_known_type(filters.resource_type)
        if filters.status is not None:
            _require_known_status(filters.status)

        learner = resolve_local_learner(self._learners)
        if learner is None:
            return ResourcePage(resources=(), total=0)

        records = self._resources.list_resources(
            learner_id=learner.id, filters=filters, limit=limit, offset=offset
        )
        return ResourcePage(
            resources=tuple(self._describe(records)),
            total=self._resources.count_resources(learner_id=learner.id, filters=filters),
        )

    def read(self, resource_id: uuid.UUID) -> ResourceDetail:
        """One of the learner's resources, with the topics it covers.

        Raises:
            ResourceNotFoundError: No such resource is stored, or it belongs to
                another learner.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        return self._describe([self._require_own_resource(resource_id)])[0]

    def update(self, resource_id: uuid.UUID, changes: ResourceChanges) -> ResourceDetail:
        """Change what a resource says, what it covers, or whether it is put aside.

        The caller owns the transaction.

        A field the request omits is left alone; an explicit clear removes what
        was stored. A supplied topic list **replaces** the link set, so a topic
        left out of one is unlinked and an empty list unlinks everything.

        **Archiving is reversible**, and it destroys nothing: `archived` puts a
        resource aside, and `registered` brings it back. Nothing in this use case
        deletes a row.

        Raises:
            ResourceNotFoundError: No such resource, or it is not the learner's.
            EmptyResourceUpdateError: The update names no field to change.
            UnknownResourceTypeError: The type is not one this build catalogues.
            UnknownResourceStatusError: A status a learner may not ask for.
            MissingResourceTitleError: The new title is empty.
            MissingResourceLocationError: The result would say where it is
                neither in words nor by a link.
            UnsupportedReferenceSchemeError: The link is not `http` or `https`.
            UnknownTopicError: A topic identifier names nothing stored.
            DuplicateTopicLinkError: A topic was named more than once.
            TooManyTopicLinksError: More topics than one request may link.
            AmbiguousLocalLearnerError: More than one learner is stored.
        """
        if changes.is_empty:
            raise EmptyResourceUpdateError(
                "The request names no field to change. Send at least one of title, "
                "resource_type, source_label, external_reference, status, or topic_ids."
            )

        record = self._require_own_resource(resource_id)

        title = record.title if changes.title is None else _require_title(changes.title)
        resource_type = record.resource_type
        if changes.resource_type is not None:
            _require_known_type(changes.resource_type)
            resource_type = changes.resource_type
        status = record.status
        if changes.status is not None:
            _require_known_status(changes.status)
            status = changes.status

        source_label = record.source_label
        if changes.clear_source_label:
            source_label = None
        elif changes.source_label is not None:
            source_label = _blank_to_none(changes.source_label)

        external_reference = record.external_reference
        if changes.clear_external_reference:
            external_reference = None
        elif changes.external_reference is not None:
            external_reference = _validated_reference(changes.external_reference)

        _require_a_location(source_label=source_label, external_reference=external_reference)

        topic_ids = None if changes.topic_ids is None else self._validated_topics(changes.topic_ids)

        changed = ResourceRecord(
            id=record.id,
            owner_learner_id=record.owner_learner_id,
            resource_type=resource_type,
            title=title,
            source_label=source_label,
            external_reference=external_reference,
            status=status,
        )
        self._resources.update_resource(changed)
        if topic_ids is not None:
            self._resources.replace_topic_links(resource_id=changed.id, topic_ids=topic_ids)
        return self._describe([changed])[0]

    def _require_learner(self) -> LearnerRecord:
        """The local learner, or a refusal naming what is missing."""
        learner = resolve_local_learner(self._learners)
        if learner is None:
            raise LearnerNotSetUpError(
                "No learner is stored, so no learning resource can be registered."
            )
        return learner

    def _require_own_resource(self, resource_id: uuid.UUID) -> ResourceRecord:
        """One of the learner's resources, or a refusal.

        A resource owned by somebody else is reported as missing rather than as
        forbidden, the rule every learner-owned read follows: saying "that exists
        but is not yours" would confirm a record the caller may not read.
        """
        learner = resolve_local_learner(self._learners)
        record = None if learner is None else self._resources.find_resource(resource_id)
        if record is None or learner is None or record.owner_learner_id != learner.id:
            raise ResourceNotFoundError(
                f"No learning resource is stored with identifier {resource_id}."
            )
        return record

    def _validated_topics(self, topic_ids: Sequence[uuid.UUID]) -> tuple[uuid.UUID, ...]:
        """The topics a request names, checked against what is stored.

        A duplicate is refused rather than collapsed, which is GOAL-005's rule
        for a day named twice: a client that sent one has a bug, and quietly
        accepting it hides the bug rather than the duplicate.
        """
        if len(topic_ids) > MAX_TOPIC_LINKS:
            raise TooManyTopicLinksError(
                f"A resource may name at most {MAX_TOPIC_LINKS} topics in one request; "
                f"{len(topic_ids)} were given."
            )
        if len(set(topic_ids)) != len(topic_ids):
            raise DuplicateTopicLinkError("A topic is named more than once. Name each one once.")

        stored = {topic.id for topic in self._resources.list_topics(topic_ids)}
        missing = [topic_id for topic_id in topic_ids if topic_id not in stored]
        if missing:
            raise UnknownTopicError(f"No topic is stored with identifier {missing[0]}.")
        return tuple(topic_ids)

    def _describe(self, records: Sequence[ResourceRecord]) -> list[ResourceDetail]:
        """Attach the topics each resource covers.

        Two queries for a whole page rather than two per resource, which is what
        keeps a catalogue of a hundred resources one round trip rather than two
        hundred.

        A link whose topic is no longer stored is left out rather than failing
        the read: the resource is the learner's, and losing a page because a
        curriculum row moved would be worse than showing one fewer topic.
        """
        links = self._resources.list_topic_links([record.id for record in records])
        named: dict[uuid.UUID, ResourceTopic] = {
            topic.id: topic
            for topic in self._resources.list_topics(
                [topic_id for ids in links.values() for topic_id in ids]
            )
        }
        return [
            ResourceDetail(
                id=record.id,
                owner_learner_id=record.owner_learner_id,
                resource_type=record.resource_type,
                title=record.title,
                source_label=record.source_label,
                external_reference=record.external_reference,
                status=record.status,
                topics=tuple(
                    named[topic_id] for topic_id in links.get(record.id, ()) if topic_id in named
                ),
            )
            for record in records
        ]


def _blank_to_none(value: str | None) -> str | None:
    """Whitespace and an absent value mean the same thing here."""
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _require_title(title: str) -> str:
    """A resource's title, or a refusal.

    Raises:
        MissingResourceTitleError: The title is empty or only whitespace.
    """
    trimmed = title.strip()
    if not trimmed:
        raise MissingResourceTitleError(
            "A learning resource needs a title, so you can find it again."
        )
    return trimmed


def _require_known_type(resource_type: str) -> None:
    """Refuse a kind of material this build does not catalogue.

    Raises:
        UnknownResourceTypeError: The type is outside `RESOURCE_TYPES`.
    """
    if resource_type not in RESOURCE_TYPES:
        raise UnknownResourceTypeError(
            f"'{resource_type}' is not a kind of learning resource. "
            f"Use one of: {', '.join(RESOURCE_TYPES)}."
        )


def _require_known_status(status: str) -> None:
    """Refuse a status a learner may not ask for.

    Raises:
        UnknownResourceStatusError: The status is outside `RESOURCE_STATUSES`.
    """
    if status not in RESOURCE_STATUSES:
        raise UnknownResourceStatusError(
            f"'{status}' is not a status you can set on a learning resource. "
            f"Use one of: {', '.join(RESOURCE_STATUSES)}."
        )


def _validated_reference(reference: str | None) -> str | None:
    """A link, checked to be a web address rather than a place on a disk.

    Raises:
        UnsupportedReferenceSchemeError: The link is not `http` or `https`, or
            names no host.
    """
    trimmed = _blank_to_none(reference)
    if trimmed is None:
        return None

    parsed = urlsplit(trimmed)
    if parsed.scheme.lower() not in REFERENCE_SCHEMES or not parsed.netloc:
        raise UnsupportedReferenceSchemeError(
            "A link must be a full http:// or https:// web address. Material that is not on "
            "the web is described in the source label instead, so no location on your own "
            "computer is stored."
        )
    return trimmed


def _require_a_location(*, source_label: str | None, external_reference: str | None) -> None:
    """Refuse a resource that says neither where it is nor what it is called.

    Raises:
        MissingResourceLocationError: Both are absent.
    """
    if source_label is None and external_reference is None:
        raise MissingResourceLocationError(
            "A learning resource needs either a link or a source label saying where the "
            "material is, so the record can lead you back to it."
        )
