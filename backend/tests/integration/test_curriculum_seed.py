"""The curriculum seed against a real PostgreSQL database.

The unit tests prove the reconcile logic against a fake. These prove the part a
fake cannot: that the writes the use case chooses actually satisfy the
constraints the migration created -- subject position uniqueness, the topic name
rule under a NULL parent, and one active version per program -- and that a
second run against real rows is genuinely a no-op.

Skipped unless ``TEST_DATABASE_URL`` names a disposable database; see
tests/integration/conftest.py.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.dto.curriculum_seed import (
    SubjectSeed,
    TopicPath,
    TopicRelationshipSeed,
    TopicSeed,
)
from app.application.use_cases.seed_curriculum import (
    ConflictingActiveCurriculumVersionError,
    SeedCurriculum,
)
from app.infrastructure.persistence.curriculum import (
    CurriculumVersion,
    LearningProgram,
    Subject,
    Topic,
    TopicRelationship,
)
from app.infrastructure.persistence.curriculum_seed_repository import (
    SqlAlchemyCurriculumSeedRepository,
)
from scripts.curriculum_seed_file import GATE_CSE_CURRICULUM_FILE, load_curriculum_seed
from tests.unit.test_seed_curriculum import build_seed

SEED_TIME = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


@pytest.fixture
def apply_seed(session: Session):
    """Apply a seed through the real repository and commit, as the script does."""

    def run(seed):
        use_case = SeedCurriculum(
            SqlAlchemyCurriculumSeedRepository(session), clock=lambda: SEED_TIME
        )
        result = use_case(seed)
        session.commit()
        return result

    return run


def count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_seed_writes_the_curriculum_to_the_database(apply_seed, session):
    result = apply_seed(build_seed())

    assert result.changed is True
    assert count(session, LearningProgram) == 1
    assert count(session, CurriculumVersion) == 1
    assert count(session, Subject) == 2
    assert count(session, Topic) == 5


def test_second_run_writes_nothing_and_keeps_every_identifier(apply_seed, session):
    seed = build_seed()
    apply_seed(seed)
    before = {row.name: row.id for row in session.scalars(select(Topic))}

    result = apply_seed(seed)

    after = {row.name: row.id for row in session.scalars(select(Topic))}
    assert result.changed is False
    assert after == before
    assert count(session, Topic) == 5


def test_repeated_runs_do_not_duplicate_curriculum_rows(apply_seed, session):
    seed = build_seed()

    for _ in range(3):
        apply_seed(seed)

    assert count(session, LearningProgram) == 1
    assert count(session, CurriculumVersion) == 1
    assert count(session, Subject) == 2
    assert count(session, Topic) == 5


def test_bundled_gate_cse_curriculum_seeds_and_reseeds_cleanly(apply_seed, session):
    seed = load_curriculum_seed(GATE_CSE_CURRICULUM_FILE)

    first = apply_seed(seed)
    topics_after_first = count(session, Topic)
    second = apply_seed(seed)

    assert first.subjects.created == 11
    assert second.changed is False
    assert count(session, Subject) == 11
    assert count(session, Topic) == topics_after_first


def test_bundled_gate_cse_version_is_active_and_published(apply_seed, session):
    apply_seed(load_curriculum_seed(GATE_CSE_CURRICULUM_FILE))

    version = session.scalar(select(CurriculumVersion))

    assert version is not None
    assert version.status == "active"
    assert version.published_at == SEED_TIME


def test_bundled_gate_cse_subject_positions_are_contiguous(apply_seed, session):
    apply_seed(load_curriculum_seed(GATE_CSE_CURRICULUM_FILE))

    positions = sorted(session.scalars(select(Subject.position)))

    assert positions == list(range(1, 12))


def test_reordering_subjects_survives_the_position_uniqueness_constraint(apply_seed, session):
    seed = build_seed()
    apply_seed(seed)

    apply_seed(build_seed(subjects=(seed.subjects[1], seed.subjects[0])))

    positions = {row.code: row.position for row in session.scalars(select(Subject))}
    assert positions == {"databases": 1, "operating-system": 2}


def test_reordering_leaves_every_subject_inside_the_position_range(apply_seed, session):
    """Vacating parks every subject on a negative position. One that does not
    move must still be written back, or it stays parked there."""
    three = (
        SubjectSeed(code="a", name="A"),
        SubjectSeed(code="b", name="B"),
        SubjectSeed(code="c", name="C"),
    )
    apply_seed(build_seed(subjects=three))

    apply_seed(build_seed(subjects=(three[1], three[0], three[2])))

    positions = {row.code: row.position for row in session.scalars(select(Subject))}
    assert positions == {"b": 1, "a": 2, "c": 3}


def test_subject_dropped_from_the_seed_is_retained_behind_the_seeded_ones(apply_seed, session):
    seed = build_seed()
    apply_seed(seed)

    apply_seed(build_seed(subjects=(seed.subjects[1],)))

    positions = {row.code: row.position for row in session.scalars(select(Subject))}
    assert positions == {"databases": 1, "operating-system": 2}
    assert count(session, Topic) == 5


def test_nested_topics_are_stored_with_their_parent(apply_seed, session):
    apply_seed(build_seed())

    parent = session.scalar(select(Topic).where(Topic.name == "Relational model"))
    children = session.scalars(
        select(Topic).where(Topic.parent_topic_id == parent.id).order_by(Topic.position)
    ).all()

    assert parent.parent_topic_id is None
    assert parent.is_trackable is False
    assert [child.name for child in children] == ["Relational algebra", "SQL"]


def test_relationships_are_stored_once_across_runs(apply_seed, session):
    seed = build_seed(
        topic_relationships=(
            TopicRelationshipSeed(
                source=TopicPath("operating-system", ("System calls",)),
                target=TopicPath("operating-system", ("Deadlock",)),
                relationship_type="prerequisite",
            ),
        )
    )

    apply_seed(seed)
    apply_seed(seed)

    assert count(session, TopicRelationship) == 1


def test_activating_a_rival_version_is_refused_before_the_database_sees_it(apply_seed, session):
    apply_seed(build_seed())

    with pytest.raises(ConflictingActiveCurriculumVersionError):
        apply_seed(build_seed(version_label="2027"))

    session.rollback()
    assert count(session, CurriculumVersion) == 1


def test_two_subjects_may_hold_topics_of_the_same_name(apply_seed, session):
    seed = build_seed(
        subjects=(
            SubjectSeed(code="a", name="A", topics=(TopicSeed(name="Trees"),)),
            SubjectSeed(code="b", name="B", topics=(TopicSeed(name="Trees"),)),
        )
    )

    apply_seed(seed)

    assert count(session, Topic) == 2
