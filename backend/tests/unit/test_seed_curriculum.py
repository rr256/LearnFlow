"""Behaviour of the curriculum seed use case.

The repeat-run assertions are the point of the file: applying the same seed
twice must report every record as unchanged and must leave every identifier
alone, because learner progress will reference those identifiers.
"""

from datetime import UTC, datetime

import pytest

from app.application.dto.curriculum_seed import (
    CurriculumSeed,
    SubjectSeed,
    TopicPath,
    TopicRelationshipSeed,
    TopicSeed,
)
from app.application.use_cases.seed_curriculum import (
    ConflictingActiveCurriculumVersionError,
    InvalidCurriculumSeedError,
    SeedCurriculum,
)
from tests.unit.fake_curriculum_seed_repository import FakeCurriculumSeedRepository

SEED_TIME = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


def build_seed(**overrides: object) -> CurriculumSeed:
    """A two-subject curriculum with one nested topic tree."""
    defaults: dict[str, object] = {
        "program_code": "gate-cse",
        "program_name": "GATE Computer Science and Information Technology",
        "program_description": "The CS paper.",
        "version_label": "2026",
        "version_status": "active",
        "source_reference": "https://example.invalid/syllabus.pdf",
        "subjects": (
            SubjectSeed(
                code="operating-system",
                name="Operating System",
                description="System calls. Deadlock.",
                topics=(
                    TopicSeed(name="System calls"),
                    TopicSeed(name="Deadlock"),
                ),
            ),
            SubjectSeed(
                code="databases",
                name="Databases",
                topics=(
                    TopicSeed(
                        name="Relational model",
                        is_trackable=False,
                        topics=(
                            TopicSeed(name="Relational algebra"),
                            TopicSeed(name="SQL"),
                        ),
                    ),
                ),
            ),
        ),
    }
    defaults.update(overrides)
    return CurriculumSeed(**defaults)  # type: ignore[arg-type]


def seed_into(repository: FakeCurriculumSeedRepository, seed: CurriculumSeed):
    use_case = SeedCurriculum(repository, clock=lambda: SEED_TIME)
    return use_case(seed)


def test_first_run_creates_the_whole_curriculum():
    repository = FakeCurriculumSeedRepository()

    result = seed_into(repository, build_seed())

    assert result.learning_program.created == 1
    assert result.curriculum_version.created == 1
    assert result.subjects.created == 2
    assert result.topics.created == 5
    assert result.changed is True
    assert len(repository.topics) == 5


def test_second_run_of_the_same_seed_changes_nothing():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed()
    seed_into(repository, seed)
    identifiers = {record.id for record in repository.topics.values()}

    result = seed_into(repository, seed)

    assert result.changed is False
    assert result.learning_program.unchanged == 1
    assert result.curriculum_version.unchanged == 1
    assert result.subjects.unchanged == 2
    assert result.topics.unchanged == 5
    assert {record.id for record in repository.topics.values()} == identifiers


def test_repeated_runs_do_not_duplicate_records():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed()

    for _ in range(3):
        seed_into(repository, seed)

    assert len(repository.programs) == 1
    assert len(repository.versions) == 1
    assert len(repository.subjects) == 2
    assert len(repository.topics) == 5


def test_changed_subject_name_updates_in_place():
    repository = FakeCurriculumSeedRepository()
    seed_into(repository, build_seed())
    original = next(r for r in repository.subjects.values() if r.code == "databases")

    renamed = build_seed(
        subjects=(
            build_seed().subjects[0],
            SubjectSeed(
                code="databases",
                name="Database Management Systems",
                topics=build_seed().subjects[1].topics,
            ),
        )
    )
    result = seed_into(repository, renamed)

    stored = repository.subjects[original.id]
    assert result.subjects.updated == 1
    assert stored.name == "Database Management Systems"
    assert stored.id == original.id


def test_topic_without_a_code_that_is_renamed_is_added_rather_than_rewritten():
    repository = FakeCurriculumSeedRepository()
    seed_into(repository, build_seed())

    renamed = build_seed(
        subjects=(
            SubjectSeed(
                code="operating-system",
                name="Operating System",
                description="System calls. Deadlock.",
                topics=(TopicSeed(name="System calls"), TopicSeed(name="Deadlocks")),
            ),
            build_seed().subjects[1],
        )
    )
    result = seed_into(repository, renamed)

    names = {record.name for record in repository.topics.values()}
    assert result.topics.created == 1
    assert {"Deadlock", "Deadlocks"} <= names


def test_topic_with_a_code_survives_a_rename():
    repository = FakeCurriculumSeedRepository()
    coded = build_seed(
        subjects=(
            SubjectSeed(
                code="operating-system",
                name="Operating System",
                topics=(TopicSeed(name="Deadlock", code="deadlock"),),
            ),
        )
    )
    seed_into(repository, coded)
    original = next(iter(repository.topics.values()))

    renamed = build_seed(
        subjects=(
            SubjectSeed(
                code="operating-system",
                name="Operating System",
                topics=(TopicSeed(name="Deadlock handling", code="deadlock"),),
            ),
        )
    )
    result = seed_into(repository, renamed)

    assert result.topics.updated == 1
    assert len(repository.topics) == 1
    assert repository.topics[original.id].name == "Deadlock handling"


def test_reordering_subjects_vacates_positions_before_reassigning_them():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed()
    seed_into(repository, seed)

    swapped = build_seed(subjects=(seed.subjects[1], seed.subjects[0]))
    result = seed_into(repository, swapped)

    positions = {record.code: record.position for record in repository.subjects.values()}
    assert repository.vacate_calls, "expected the position range to be cleared before reassigning"
    assert positions == {"databases": 1, "operating-system": 2}
    assert result.subjects.updated == 2


def test_subjects_that_stay_put_are_restored_after_a_vacate():
    """Vacating moves every subject out of the position range, so a subject
    whose position is unchanged still has to be written back. Missing this
    leaves it parked at a negative position."""
    repository = FakeCurriculumSeedRepository()
    three = (
        SubjectSeed(code="a", name="A"),
        SubjectSeed(code="b", name="B"),
        SubjectSeed(code="c", name="C"),
    )
    seed_into(repository, build_seed(subjects=three))

    # Swap the first two; "c" keeps position 3 throughout.
    result = seed_into(repository, build_seed(subjects=(three[1], three[0], three[2])))

    positions = {record.code: record.position for record in repository.subjects.values()}
    assert positions == {"b": 1, "a": 2, "c": 3}
    assert result.subjects.updated == 2
    assert result.subjects.unchanged == 1


def test_reordering_leaves_no_subject_outside_the_position_range():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed()
    seed_into(repository, seed)

    seed_into(repository, build_seed(subjects=(seed.subjects[1], seed.subjects[0])))

    assert all(record.position > 0 for record in repository.subjects.values())


def test_unchanged_ordering_does_not_vacate_positions():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed()
    seed_into(repository, seed)

    seed_into(repository, seed)

    assert repository.vacate_calls == []


def test_subject_dropped_from_the_seed_is_kept_and_moved_to_the_end():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed()
    seed_into(repository, seed)

    shrunk = build_seed(subjects=(seed.subjects[1],))
    seed_into(repository, shrunk)

    positions = {record.code: record.position for record in repository.subjects.values()}
    assert positions == {"databases": 1, "operating-system": 2}
    assert len(repository.subjects) == 2


def test_topics_of_a_dropped_subject_are_not_deleted():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed()
    seed_into(repository, seed)

    seed_into(repository, build_seed(subjects=(seed.subjects[1],)))

    assert len(repository.topics) == 5


def test_nested_topics_are_positioned_within_their_parent():
    repository = FakeCurriculumSeedRepository()
    seed_into(repository, build_seed())

    parent = next(r for r in repository.topics.values() if r.name == "Relational model")
    children = sorted(
        (r for r in repository.topics.values() if r.parent_topic_id == parent.id),
        key=lambda record: record.position,
    )

    assert parent.parent_topic_id is None
    assert parent.is_trackable is False
    assert [record.name for record in children] == ["Relational algebra", "SQL"]
    assert [record.position for record in children] == [1, 2]
    assert all(record.is_trackable for record in children)


def test_active_version_is_stamped_with_the_publication_time_once():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed()

    seed_into(repository, seed)
    stamped = next(iter(repository.versions.values())).published_at

    later = SeedCurriculum(repository, clock=lambda: datetime(2027, 1, 1, tzinfo=UTC))
    later(seed)

    assert stamped == SEED_TIME
    assert next(iter(repository.versions.values())).published_at == SEED_TIME


def test_draft_version_is_not_stamped():
    repository = FakeCurriculumSeedRepository()

    seed_into(repository, build_seed(version_status="draft"))

    assert next(iter(repository.versions.values())).published_at is None


def test_seed_may_state_its_own_publication_time():
    repository = FakeCurriculumSeedRepository()
    published = datetime(2025, 8, 21, tzinfo=UTC)

    seed_into(repository, build_seed(published_at=published))

    assert next(iter(repository.versions.values())).published_at == published


def test_activating_a_second_version_is_refused():
    repository = FakeCurriculumSeedRepository()
    seed_into(repository, build_seed())

    with pytest.raises(ConflictingActiveCurriculumVersionError) as error:
        seed_into(repository, build_seed(version_label="2027"))

    assert "'2026'" in str(error.value)
    assert len(repository.versions) == 1


def test_a_second_version_may_be_seeded_as_a_draft():
    repository = FakeCurriculumSeedRepository()
    seed_into(repository, build_seed())

    seed_into(repository, build_seed(version_label="2027", version_status="draft"))

    assert len(repository.versions) == 2


def test_relationships_are_created_once_and_then_left_alone():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed(
        topic_relationships=(
            TopicRelationshipSeed(
                source=TopicPath("operating-system", ("System calls",)),
                target=TopicPath("operating-system", ("Deadlock",)),
                relationship_type="prerequisite",
            ),
        )
    )

    first = seed_into(repository, seed)
    second = seed_into(repository, seed)

    assert first.topic_relationships.created == 1
    assert second.topic_relationships.unchanged == 1
    assert len(repository.relationships) == 1


def test_relationship_may_reference_a_nested_topic():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed(
        topic_relationships=(
            TopicRelationshipSeed(
                source=TopicPath("databases", ("Relational model", "Relational algebra")),
                target=TopicPath("databases", ("Relational model", "SQL")),
                relationship_type="recommended_before",
            ),
        )
    )

    result = seed_into(repository, seed)

    assert result.topic_relationships.created == 1


def test_relationship_to_an_undefined_topic_is_rejected():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed(
        topic_relationships=(
            TopicRelationshipSeed(
                source=TopicPath("operating-system", ("System calls",)),
                target=TopicPath("operating-system", ("Paging",)),
                relationship_type="prerequisite",
            ),
        )
    )

    with pytest.raises(InvalidCurriculumSeedError, match="Paging"):
        seed_into(repository, seed)


def test_relationship_from_a_topic_to_itself_is_rejected():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed(
        topic_relationships=(
            TopicRelationshipSeed(
                source=TopicPath("operating-system", ("Deadlock",)),
                target=TopicPath("operating-system", ("Deadlock",)),
                relationship_type="related",
            ),
        )
    )

    with pytest.raises(InvalidCurriculumSeedError, match="itself"):
        seed_into(repository, seed)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"version_status": "published"}, "status"),
        ({"subjects": ()}, "at least one subject"),
    ],
)
def test_malformed_seed_is_rejected(overrides, message):
    repository = FakeCurriculumSeedRepository()

    with pytest.raises(InvalidCurriculumSeedError, match=message):
        seed_into(repository, build_seed(**overrides))


def test_duplicate_subject_code_is_rejected():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed(
        subjects=(
            SubjectSeed(code="databases", name="Databases"),
            SubjectSeed(code="databases", name="Databases again"),
        )
    )

    with pytest.raises(InvalidCurriculumSeedError, match="Duplicate subject code"):
        seed_into(repository, seed)


def test_duplicate_sibling_topic_name_is_rejected():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed(
        subjects=(
            SubjectSeed(
                code="databases",
                name="Databases",
                topics=(TopicSeed(name="Indexing"), TopicSeed(name="Indexing")),
            ),
        )
    )

    with pytest.raises(InvalidCurriculumSeedError, match="Duplicate topic name"):
        seed_into(repository, seed)


def test_the_same_topic_name_may_appear_under_different_parents():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed(
        subjects=(
            SubjectSeed(
                code="databases",
                name="Databases",
                topics=(
                    TopicSeed(
                        name="Indexing",
                        is_trackable=False,
                        topics=(TopicSeed(name="B+ trees"),),
                    ),
                    TopicSeed(
                        name="Storage",
                        is_trackable=False,
                        topics=(TopicSeed(name="B+ trees"),),
                    ),
                ),
            ),
        )
    )

    result = seed_into(repository, seed)

    assert result.topics.created == 4


def test_unknown_relationship_type_is_rejected():
    repository = FakeCurriculumSeedRepository()
    seed = build_seed(
        topic_relationships=(
            TopicRelationshipSeed(
                source=TopicPath("operating-system", ("System calls",)),
                target=TopicPath("operating-system", ("Deadlock",)),
                relationship_type="follows",
            ),
        )
    )

    with pytest.raises(InvalidCurriculumSeedError, match="relationship type"):
        seed_into(repository, seed)


def test_nothing_is_written_when_the_seed_is_invalid():
    repository = FakeCurriculumSeedRepository()

    with pytest.raises(InvalidCurriculumSeedError):
        seed_into(repository, build_seed(version_status="published"))

    assert repository.programs == {}
    assert repository.versions == {}
