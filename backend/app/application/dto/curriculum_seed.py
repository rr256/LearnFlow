"""Input and output structures for seeding a curated curriculum.

The seed describes a whole curriculum version as a single immutable value: the
learning program it belongs to, the version's identity and publication state,
its subjects, and the topic tree under each subject. Nothing here knows how the
curriculum is stored or where the description came from.

Order carries meaning. A subject's `position` is its index in `subjects`, and a
topic's `position` is its index among its siblings, so re-ordering the source
re-orders the curriculum without a second field that could disagree with it.
"""

from dataclasses import dataclass, field
from datetime import datetime

CURRICULUM_VERSION_STATUSES: tuple[str, ...] = ("draft", "active", "retired")
"""Statuses `curriculum_versions.status` accepts, per docs/database/schema.md."""

TOPIC_RELATIONSHIP_TYPES: tuple[str, ...] = ("prerequisite", "recommended_before", "related")
"""Relationship types `topic_relationships.relationship_type` accepts."""


@dataclass(frozen=True, slots=True)
class TopicSeed:
    """One topic, and the subtopics nested under it."""

    name: str
    code: str | None = None
    description: str | None = None
    is_trackable: bool = True
    topics: tuple[TopicSeed, ...] = ()


@dataclass(frozen=True, slots=True)
class SubjectSeed:
    """One subject and its topic tree."""

    code: str
    name: str
    description: str | None = None
    topics: tuple[TopicSeed, ...] = ()


@dataclass(frozen=True, slots=True)
class TopicPath:
    """Locates a topic by the names that lead to it from its subject.

    A path rather than an identifier, because the seed source is authored before
    any identifier exists. ``names`` walks the topic tree from the subject's root
    downward, so ``("Discrete Mathematics", "Monoids, Groups")`` is a subtopic
    and ``("Deadlock",)`` is a root topic.
    """

    subject_code: str
    names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TopicRelationshipSeed:
    """A prerequisite or sequencing edge between two topics of this version."""

    source: TopicPath
    target: TopicPath
    relationship_type: str


@dataclass(frozen=True, slots=True)
class CurriculumSeed:
    """A complete curated curriculum version, ready to be applied."""

    program_code: str
    program_name: str
    version_label: str
    version_status: str
    program_description: str | None = None
    source_reference: str | None = None
    published_at: datetime | None = None
    subjects: tuple[SubjectSeed, ...] = ()
    topic_relationships: tuple[TopicRelationshipSeed, ...] = ()


@dataclass(frozen=True, slots=True)
class SeedOutcome:
    """How one kind of record fared: how many were written, and how many already matched."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0

    @property
    def changed(self) -> bool:
        """Whether applying the seed wrote anything for this kind of record."""
        return bool(self.created or self.updated)

    def with_created(self) -> SeedOutcome:
        """This outcome plus one created record."""
        return SeedOutcome(self.created + 1, self.updated, self.unchanged)

    def with_updated(self) -> SeedOutcome:
        """This outcome plus one updated record."""
        return SeedOutcome(self.created, self.updated + 1, self.unchanged)

    def with_unchanged(self) -> SeedOutcome:
        """This outcome plus one record that already matched the seed."""
        return SeedOutcome(self.created, self.updated, self.unchanged + 1)


@dataclass(frozen=True, slots=True)
class CurriculumSeedResult:
    """What applying a seed did, one outcome per kind of record.

    A second run of an unchanged seed reports every outcome as unchanged, which
    is what the idempotency tests assert against.
    """

    learning_program: SeedOutcome = field(default_factory=SeedOutcome)
    curriculum_version: SeedOutcome = field(default_factory=SeedOutcome)
    subjects: SeedOutcome = field(default_factory=SeedOutcome)
    topics: SeedOutcome = field(default_factory=SeedOutcome)
    topic_relationships: SeedOutcome = field(default_factory=SeedOutcome)

    @property
    def changed(self) -> bool:
        """Whether the run wrote anything at all."""
        return any(
            outcome.changed
            for outcome in (
                self.learning_program,
                self.curriculum_version,
                self.subjects,
                self.topics,
                self.topic_relationships,
            )
        )
