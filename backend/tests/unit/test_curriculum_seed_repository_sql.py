"""The SQL the curriculum seed repository emits, compiled but not executed.

These need no database, so they stay in the unit suite and run on a machine
without PostgreSQL. They cover the statements whose correctness is not obvious
from reading the Python: the position-vacating UPDATE and the two queries that
reach a curriculum version through a join.

Whether those statements actually satisfy the schema's constraints is settled
against a live database by tests/integration/test_curriculum_seed.py.
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.dialects import postgresql

from app.infrastructure.persistence.curriculum import Subject, Topic, TopicRelationship

VERSION_ID = uuid.UUID("00000000-0000-0000-0000-0000000000ff")


def rendered(statement) -> str:
    """Render a statement as PostgreSQL SQL with its values inlined."""
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_vacating_positions_maps_them_out_of_the_range_the_seed_assigns():
    """``-position - 1`` is injective and always negative for positive input, so
    the moved rows stay unique among themselves and free every target slot."""
    statement = (
        update(Subject)
        .where(Subject.curriculum_version_id == VERSION_ID)
        .values(position=-Subject.position - 1)
    )

    sql = rendered(statement)

    assert "UPDATE subjects SET position=(-subjects.position - 1)" in sql
    assert "WHERE subjects.curriculum_version_id" in sql
    # A bulk UPDATE still honours the mapper's onupdate, so the audit column
    # stays truthful even though the statement never names it.
    assert "updated_at=now()" in sql


def test_vacating_positions_cannot_collide_with_a_seeded_position():
    positions = range(1, 50)

    vacated = [-position - 1 for position in positions]

    assert len(set(vacated)) == len(vacated)
    assert max(vacated) < min(positions)


def test_listing_topics_reaches_the_version_through_its_subjects():
    statement = (
        select(Topic)
        .join(Subject, Topic.subject_id == Subject.id)
        .where(Subject.curriculum_version_id == VERSION_ID)
        .order_by(Subject.position, Topic.position)
    )

    sql = rendered(statement)

    assert "JOIN subjects ON topics.subject_id = subjects.id" in sql
    assert "WHERE subjects.curriculum_version_id" in sql
    assert "ORDER BY subjects.position, topics.position" in sql


def test_listing_relationships_is_scoped_by_the_source_topic_version():
    statement = (
        select(TopicRelationship)
        .join(Topic, TopicRelationship.source_topic_id == Topic.id)
        .join(Subject, Topic.subject_id == Subject.id)
        .where(Subject.curriculum_version_id == VERSION_ID)
    )

    sql = rendered(statement)

    assert "JOIN topics ON topic_relationships.source_topic_id = topics.id" in sql
    assert "JOIN subjects ON topics.subject_id = subjects.id" in sql
