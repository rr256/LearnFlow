"""Apply a curated curriculum to the store, safely and repeatably.

Running this twice with the same seed must leave the database exactly as the
first run left it, because reference data is loaded by hand, in migrations
rehearsals, in CI, and after every restore. The rule that makes that hold is
match-then-compare: every record is located by a natural key, written only when
a field actually differs, and never deleted.

Nothing is removed. Curriculum rows are reference data that learner progress,
plans, and assessment evidence will point at (docs/database/schema.md), so a
subject or topic dropped from the source file is left in place rather than
deleted out from under a learner. Subjects that disappear from the source are
moved to the end of the ordering so the seeded ones stay contiguous.

Natural keys, each matching a uniqueness rule the database already enforces:

    learning program     code
    curriculum version   (learning program, version label)
    subject              (curriculum version, code)
    topic                (subject, code) when the seed gives a code,
                         otherwise (subject, parent topic, name)
    topic relationship   (source topic, target topic, relationship type)

A topic renamed in the source therefore reads as a new topic unless it carries a
code. That is deliberate: without a code there is nothing to tell a rename apart
from a genuinely new topic, and inventing the distinction would silently rewrite
a topic that learner progress may already reference.
"""

import uuid
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime

from app.application.dto.curriculum_seed import (
    CURRICULUM_VERSION_STATUSES,
    TOPIC_RELATIONSHIP_TYPES,
    CurriculumSeed,
    CurriculumSeedResult,
    SeedOutcome,
    SubjectSeed,
    TopicPath,
    TopicSeed,
)
from app.application.ports.curriculum_seed_repository import (
    CurriculumSeedRepository,
    CurriculumVersionRecord,
    LearningProgramRecord,
    SubjectRecord,
    TopicRecord,
    TopicRelationshipRecord,
)

ACTIVE_STATUS = "active"


class CurriculumSeedError(Exception):
    """A curriculum seed could not be applied."""


class InvalidCurriculumSeedError(CurriculumSeedError):
    """The seed contradicts itself or the vocabulary the schema accepts."""


class ConflictingActiveCurriculumVersionError(CurriculumSeedError):
    """Another version of the program is already active.

    A program has at most one active curriculum version, enforced by a partial
    unique index (ADR-011). Seeding a second one is refused here, naming both
    versions, rather than left to surface as an integrity error.
    """


class SeedCurriculum:
    """Applies a `CurriculumSeed` through a `CurriculumSeedRepository`."""

    def __init__(
        self,
        repository: CurriculumSeedRepository,
        *,
        clock: Callable[[], datetime],
    ) -> None:
        """Wire the use case.

        Args:
            repository: Where curriculum records are read and written.
            clock: Supplies "now" for the publication timestamp of a version
                that becomes active without the seed naming one. Injected so a
                test can pin it and so the use case reads no ambient state.
        """
        self._repository = repository
        self._clock = clock

    def __call__(self, seed: CurriculumSeed) -> CurriculumSeedResult:
        """Apply `seed`, returning what was created, updated, and left alone.

        The caller owns the transaction: this method writes through the
        repository but never commits, so a failure part-way leaves nothing
        behind.

        Raises:
            InvalidCurriculumSeedError: The seed is internally inconsistent.
            ConflictingActiveCurriculumVersionError: A different version of the
                program is already active.
        """
        _validate(seed)

        program, program_outcome = self._apply_program(seed)
        version, version_outcome = self._apply_version(seed, program.id)
        subjects, subject_outcome = self._apply_subjects(seed, version.id)
        topics, topic_outcome = self._apply_topics(seed, version.id, subjects)
        relationship_outcome = self._apply_relationships(seed, version.id, topics)

        return CurriculumSeedResult(
            learning_program=program_outcome,
            curriculum_version=version_outcome,
            subjects=subject_outcome,
            topics=topic_outcome,
            topic_relationships=relationship_outcome,
        )

    # -- learning program ---------------------------------------------------

    def _apply_program(self, seed: CurriculumSeed) -> tuple[LearningProgramRecord, SeedOutcome]:
        existing = self._repository.find_learning_program(seed.program_code)
        if existing is None:
            record = LearningProgramRecord(
                id=uuid.uuid4(),
                code=seed.program_code,
                name=seed.program_name,
                description=seed.program_description,
            )
            self._repository.add_learning_program(record)
            return record, SeedOutcome().with_created()

        desired = LearningProgramRecord(
            id=existing.id,
            code=existing.code,
            name=seed.program_name,
            description=seed.program_description,
        )
        if desired == existing:
            return existing, SeedOutcome().with_unchanged()
        self._repository.update_learning_program(desired)
        return desired, SeedOutcome().with_updated()

    # -- curriculum version -------------------------------------------------

    def _apply_version(
        self, seed: CurriculumSeed, program_id: uuid.UUID
    ) -> tuple[CurriculumVersionRecord, SeedOutcome]:
        existing = self._repository.find_curriculum_version(
            learning_program_id=program_id, version_label=seed.version_label
        )
        if seed.version_status == ACTIVE_STATUS:
            self._reject_rival_active_version(program_id, seed.version_label, existing)

        if existing is None:
            record = CurriculumVersionRecord(
                id=uuid.uuid4(),
                learning_program_id=program_id,
                version_label=seed.version_label,
                status=seed.version_status,
                source_reference=seed.source_reference,
                published_at=self._publication_time(seed, previous=None),
            )
            self._repository.add_curriculum_version(record)
            return record, SeedOutcome().with_created()

        desired = CurriculumVersionRecord(
            id=existing.id,
            learning_program_id=existing.learning_program_id,
            version_label=existing.version_label,
            status=seed.version_status,
            source_reference=seed.source_reference,
            published_at=self._publication_time(seed, previous=existing.published_at),
        )
        if desired == existing:
            return existing, SeedOutcome().with_unchanged()
        self._repository.update_curriculum_version(desired)
        return desired, SeedOutcome().with_updated()

    def _reject_rival_active_version(
        self,
        program_id: uuid.UUID,
        version_label: str,
        existing: CurriculumVersionRecord | None,
    ) -> None:
        active = self._repository.find_active_curriculum_version(program_id)
        if active is None or (existing is not None and active.id == existing.id):
            return
        raise ConflictingActiveCurriculumVersionError(
            f"Cannot activate curriculum version {version_label!r}: version "
            f"{active.version_label!r} of the same learning program is already active. "
            "Retire it first, or seed this version with status 'draft'."
        )

    def _publication_time(
        self, seed: CurriculumSeed, *, previous: datetime | None
    ) -> datetime | None:
        """When this version became active.

        A seed that names the time wins. Otherwise an already-recorded time is
        kept -- overwriting it on every run would make the seed report a change
        it did not make -- and a version becoming active without one is stamped
        now.
        """
        if seed.published_at is not None:
            return seed.published_at
        if previous is not None:
            return previous
        return self._clock() if seed.version_status == ACTIVE_STATUS else None

    # -- subjects -----------------------------------------------------------

    def _apply_subjects(
        self, seed: CurriculumSeed, version_id: uuid.UUID
    ) -> tuple[dict[str, SubjectRecord], SeedOutcome]:
        existing = self._repository.list_subjects(version_id)
        by_code = {record.code: record for record in existing}
        seeded_codes = {subject.code for subject in seed.subjects}

        desired: list[SubjectRecord] = []
        for position, subject in enumerate(seed.subjects, start=1):
            match = by_code.get(subject.code)
            desired.append(
                SubjectRecord(
                    id=match.id if match else uuid.uuid4(),
                    curriculum_version_id=version_id,
                    code=subject.code,
                    name=subject.name,
                    description=subject.description,
                    position=position,
                )
            )

        # Subjects the source no longer lists keep their rows and their relative
        # order, but move behind the seeded ones so the seeded positions stay
        # contiguous and cannot collide.
        retired = sorted(
            (record for record in existing if record.code not in seeded_codes),
            key=lambda record: record.position,
        )
        for offset, record in enumerate(retired, start=len(seed.subjects) + 1):
            desired.append(
                SubjectRecord(
                    id=record.id,
                    curriculum_version_id=record.curriculum_version_id,
                    code=record.code,
                    name=record.name,
                    description=record.description,
                    position=offset,
                )
            )

        moves = any(
            (match := by_code.get(record.code)) is not None and match.position != record.position
            for record in desired
        )
        if moves:
            # At least one subject changes position. Positions are unique per
            # version and checked per statement, so clear the range before
            # re-assigning it; otherwise two subjects swapping places collide.
            self._repository.vacate_subject_positions(version_id)
            self._repository.flush()

        outcome = SeedOutcome()
        for record in desired:
            match = by_code.get(record.code)
            if match is None:
                self._repository.add_subject(record)
                outcome = outcome.with_created()
            elif match == record:
                # Its final state is what was already stored, so the run reports
                # it as unchanged. It still needs writing when positions were
                # vacated, because vacating moved every row out of the range and
                # this one would otherwise be left parked outside it.
                if moves:
                    self._repository.update_subject(record)
                outcome = outcome.with_unchanged()
            else:
                self._repository.update_subject(record)
                outcome = outcome.with_updated()

        return {record.code: record for record in desired}, outcome

    # -- topics -------------------------------------------------------------

    def _apply_topics(
        self,
        seed: CurriculumSeed,
        version_id: uuid.UUID,
        subjects: dict[str, SubjectRecord],
    ) -> tuple[dict[tuple[str, tuple[str, ...]], TopicRecord], SeedOutcome]:
        existing = self._repository.list_topics(version_id)
        by_code = {(record.subject_id, record.code): record for record in existing if record.code}
        by_name = {
            (record.subject_id, record.parent_topic_id, record.name): record for record in existing
        }

        resolved: dict[tuple[str, tuple[str, ...]], TopicRecord] = {}
        outcome = SeedOutcome()

        def walk(
            subject: SubjectSeed,
            topics: Sequence[TopicSeed],
            parent_id: uuid.UUID | None,
            trail: tuple[str, ...],
        ) -> None:
            nonlocal outcome
            subject_id = subjects[subject.code].id
            for position, topic in enumerate(topics, start=1):
                match = by_code.get((subject_id, topic.code)) if topic.code else None
                if match is None:
                    match = by_name.get((subject_id, parent_id, topic.name))

                record = TopicRecord(
                    id=match.id if match else uuid.uuid4(),
                    subject_id=subject_id,
                    parent_topic_id=parent_id,
                    code=topic.code,
                    name=topic.name,
                    description=topic.description,
                    position=position,
                    is_trackable=topic.is_trackable,
                )
                if match is None:
                    self._repository.add_topic(record)
                    outcome = outcome.with_created()
                elif match == record:
                    outcome = outcome.with_unchanged()
                else:
                    self._repository.update_topic(record)
                    outcome = outcome.with_updated()

                path = trail + (topic.name,)
                resolved[(subject.code, path)] = record
                walk(subject, topic.topics, record.id, path)

        for subject in seed.subjects:
            walk(subject, subject.topics, None, ())

        return resolved, outcome

    # -- topic relationships ------------------------------------------------

    def _apply_relationships(
        self,
        seed: CurriculumSeed,
        version_id: uuid.UUID,
        topics: dict[tuple[str, tuple[str, ...]], TopicRecord],
    ) -> SeedOutcome:
        if not seed.topic_relationships:
            return SeedOutcome()

        existing = {
            (record.source_topic_id, record.target_topic_id, record.relationship_type)
            for record in self._repository.list_topic_relationships(version_id)
        }

        outcome = SeedOutcome()
        for relationship in seed.topic_relationships:
            source = _resolve_topic(topics, relationship.source)
            target = _resolve_topic(topics, relationship.target)
            if source.id == target.id:
                raise InvalidCurriculumSeedError(
                    f"Topic relationship {relationship.relationship_type!r} links "
                    f"{_describe(relationship.source)} to itself."
                )

            key = (source.id, target.id, relationship.relationship_type)
            if key in existing:
                outcome = outcome.with_unchanged()
                continue
            self._repository.add_topic_relationship(
                TopicRelationshipRecord(
                    source_topic_id=source.id,
                    target_topic_id=target.id,
                    relationship_type=relationship.relationship_type,
                )
            )
            existing.add(key)
            outcome = outcome.with_created()

        return outcome


def _resolve_topic(
    topics: dict[tuple[str, tuple[str, ...]], TopicRecord], path: TopicPath
) -> TopicRecord:
    record = topics.get((path.subject_code, path.names))
    if record is None:
        raise InvalidCurriculumSeedError(
            f"Topic relationship refers to {_describe(path)}, which the seed does not define."
        )
    return record


def _describe(path: TopicPath) -> str:
    return f"{path.subject_code}:{' > '.join(path.names)}"


def _validate(seed: CurriculumSeed) -> None:
    """Reject a seed the database would refuse, or that hides an authoring slip."""
    if seed.version_status not in CURRICULUM_VERSION_STATUSES:
        raise InvalidCurriculumSeedError(
            f"Unknown curriculum version status {seed.version_status!r}. "
            f"Expected one of {', '.join(CURRICULUM_VERSION_STATUSES)}."
        )
    if not seed.subjects:
        raise InvalidCurriculumSeedError("A curriculum seed must define at least one subject.")

    _reject_duplicates(
        (subject.code for subject in seed.subjects),
        "subject code",
    )
    for subject in seed.subjects:
        _validate_topics(subject.code, subject.topics, ())

    for relationship in seed.topic_relationships:
        if relationship.relationship_type not in TOPIC_RELATIONSHIP_TYPES:
            raise InvalidCurriculumSeedError(
                f"Unknown topic relationship type {relationship.relationship_type!r}. "
                f"Expected one of {', '.join(TOPIC_RELATIONSHIP_TYPES)}."
            )


def _validate_topics(
    subject_code: str, topics: Sequence[TopicSeed], trail: tuple[str, ...]
) -> None:
    where = f"subject {subject_code!r}" + (f" under {' > '.join(trail)}" if trail else "")
    # Siblings share the (subject, parent, name) uniqueness rule the database
    # enforces, so a duplicate here would fail on write rather than on review.
    _reject_duplicates((topic.name for topic in topics), "topic name", where)
    _reject_duplicates((topic.code for topic in topics if topic.code), "topic code", where)
    for topic in topics:
        _validate_topics(subject_code, topic.topics, trail + (topic.name,))


def _reject_duplicates(values: Iterable[str], label: str, where: str = "") -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            location = f" in {where}" if where else ""
            raise InvalidCurriculumSeedError(f"Duplicate {label} {value!r}{location}.")
        seen.add(value)
