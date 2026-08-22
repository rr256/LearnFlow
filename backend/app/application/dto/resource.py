"""Input and output structures for a learner's learning resources.

These carry what RES-001 to RES-004 register, read, and change. They are
framework-independent by design, as the other DTOs in this package are: the API
schemas that serialise them are a separate representation, so a change to the
HTTP contract does not reach back into the use case.

A learning resource is learner-owned and may name one or more topics. Nothing
inbound carries a `learner_id`: the effective learner is resolved server-side
(docs/api/conventions.md).

The controlled values below mirror the `CHECK` constraints on `resources` and
`resource_topic_links`, the way `LEARNING_STAGES`, `WEEKDAYS`, and the plan and
revision vocabularies mirror theirs. A value the application forgot to check is
refused by the database rather than stored and trusted later.
"""

import uuid
from dataclasses import dataclass, field

RESOURCE_TYPES: tuple[str, ...] = ("pdf", "note", "pyq", "formula_sheet", "video_reference")
"""The kinds of study material a learner may catalogue.

Five of the seven docs/database/schema.md documents. `image` and `attachment`
are deliberately absent: both name an uploaded file, and nothing uploads one —
this catalogue records **where material is**, not the material itself. They
arrive with the storage and ingestion change that gives a file somewhere to
live, which is the rule ADR-011 applies to a column and ADR-028 applied to
`trigger_type`.
"""

RESOURCE_STATUSES: tuple[str, ...] = ("registered", "archived")
"""The statuses `resources.status` accepts.

Two of the five docs/database/schema.md documents. `processing`, `ready`, and
`failed` are **ingestion lifecycle states**, and `resource_ingestions` does not
exist: a status nothing can move a resource into would be a promise the database
cannot keep. They arrive with the ingestion change, which needs a migration for
its own table regardless.

`registered` is what every resource is written as. `archived` is the learner
putting one aside, and it is reversible — nothing here destroys a record.
"""

RESOURCE_TOPIC_ROLES: tuple[str, ...] = ("primary", "supporting", "practice", "revision")
"""What a resource is to the topic it is linked to.

All four docs/database/schema.md documents, and the reason they are all carried
where two resource statuses are not: choosing between these needs no storage
that does not exist, so offering them later is a use-case change rather than a
migration — the argument ADR-020 made for `plan_items.status`, which paid off
three times.

**Only `primary` is written today.** A learner links material to a topic; they
are not asked to grade how central it is, because nothing would read the answer
and the question invites a judgement the product has no use for.
"""

REGISTERED = "registered"
ARCHIVED = "archived"
PRIMARY = "primary"

MAX_TOPIC_LINKS = 100
"""How many topics one resource may name in a single request.

A bound rather than a rule about study: it stops one request writing an unbounded
number of rows. It sits above the 65 topics and subtopics of the whole curated
GATE CSE curriculum, so no honest link set is refused by it.
"""


@dataclass(frozen=True, slots=True)
class ResourceTopic:
    """A topic a resource is linked to, named well enough to display."""

    id: uuid.UUID
    code: str | None
    name: str
    subject_id: uuid.UUID
    subject_name: str


@dataclass(frozen=True, slots=True)
class ResourceRecord:
    """One learning resource, as stored.

    The persistence shape, used by the port. `ResourceDetail` below is what a
    caller reads.

    There is no `storage_key` and no `metadata`: nothing uploads a file, so both
    would be columns no code maintains — the trap ADR-011 exists to avoid, and
    the reason `learner_topic_progress` was created without three of its
    documented columns.
    """

    id: uuid.UUID
    owner_learner_id: uuid.UUID | None
    resource_type: str
    title: str
    source_label: str | None
    external_reference: str | None
    status: str


@dataclass(frozen=True, slots=True)
class ResourceDetail:
    """One learning resource as a learner reads it, with the topics it covers.

    `topics` is carried on a listed resource as well as on a read one, unlike a
    study plan's `items`: a link set is bounded at `MAX_TOPIC_LINKS` and naming
    what a resource covers is the whole point of the catalogue, where a page of
    plans each carrying every item would be an unbounded payload inside a
    paginated one.
    """

    id: uuid.UUID
    owner_learner_id: uuid.UUID | None
    resource_type: str
    title: str
    source_label: str | None
    external_reference: str | None
    status: str
    topics: tuple[ResourceTopic, ...] = ()


@dataclass(frozen=True, slots=True)
class ResourcePage:
    """One page of learning resources, with the total the pagination block reports."""

    resources: tuple[ResourceDetail, ...]
    total: int


@dataclass(frozen=True, slots=True)
class ResourceFilters:
    """What a caller may narrow a resource list by.

    `topic_id` is what answers FR-007's fourth acceptance criterion — finding the
    resources associated with a topic — at the API rather than by a client
    filtering a whole collection it happened to hold.

    There is deliberately no `subject_id`. It is a compatible addition under
    docs/api/versioning.md, and it arrives with a screen that needs it; neither
    screen reading this endpoint does, because both want the collection whole and
    join it by topic identifier, which is the position PRG-002 takes.
    """

    topic_id: uuid.UUID | None = None
    resource_type: str | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class NewResource:
    """A learning resource a learner is asking to register (RES-001).

    There is no `status`: a resource is written `registered`, and archiving it is
    a later statement made through RES-004. That is the shape PLN-004 uses for a
    plan item, where the status a record is created in is not a request field.

    Attributes:
        resource_type: One of `RESOURCE_TYPES`.
        title: What the learner calls this material.
        source_label: Where it is, in the learner's own words — a book and
            chapter, a folder they keep, a lecture series. This is what carries
            offline material, which is why a resource needs no link.
        external_reference: An `http` or `https` address. Nothing about the
            learner's own machine is stored here; see the use case.
        topic_ids: The curriculum topics this material covers, at most
            `MAX_TOPIC_LINKS` of them.
    """

    resource_type: str
    title: str
    source_label: str | None = None
    external_reference: str | None = None
    topic_ids: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class ResourceChanges:
    """The fields a resource update asks to change (RES-004).

    A field left unset is not touched. Clearing needs its own flag for the two
    fields that can be cleared, for the reason `StudyGoalChanges` records: a
    nullable field alone cannot say whether `None` means "leave it" or "remove
    it", and guessing wrong silently discards what the learner wrote.

    `topic_ids` needs **no such flag**, and the asymmetry is the one GOAL-004
    draws for a preference group. A supplied list replaces the whole link set, so
    an empty list is a distinct value from no list at all: `None` can mean "leave
    the links alone" without "unlink everything" becoming inexpressible.

    `title` and `resource_type` carry no flag either, because neither can be
    cleared — a resource always has both, the rule LRN-002 applies to a timezone
    and GOAL-004 to a status.
    """

    title: str | None = None
    resource_type: str | None = None
    source_label: str | None = None
    clear_source_label: bool = False
    external_reference: str | None = None
    clear_external_reference: bool = False
    status: str | None = None
    topic_ids: tuple[uuid.UUID, ...] | None = None

    @property
    def is_empty(self) -> bool:
        """Whether the update asks for nothing at all."""
        return (
            self.title is None
            and self.resource_type is None
            and self.source_label is None
            and not self.clear_source_label
            and self.external_reference is None
            and not self.clear_external_reference
            and self.status is None
            and self.topic_ids is None
        )


@dataclass(frozen=True, slots=True)
class ResourceTopicLinks:
    """The topics one resource covers, as the repository writes them.

    Every link is written with `relationship_type = PRIMARY`; the other three
    roles are constrained and unwritten, for the reason `RESOURCE_TOPIC_ROLES`
    gives.
    """

    resource_id: uuid.UUID
    topic_ids: tuple[uuid.UUID, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class RemovedResource:
    """What removing one resource destroyed (RES-005).

    Returned so the caller can state the loss in words without counting it a
    second time. **These are not a measure of the learner** -- terminology's
    no-counting rule is about progress and effort, and this describes what a
    destructive action just destroyed. Nothing here is stored, totalled across
    resources, or shown as progress.
    """

    resource_id: uuid.UUID
    title: str
    notes_removed: int
    files_removed: int
    bytes_unlinked: int
