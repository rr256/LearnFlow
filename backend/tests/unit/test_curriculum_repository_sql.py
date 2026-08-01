"""The SQL the read-only curriculum repository emits, compiled but not executed.

These need no database, so they stay in the unit suite and run on a machine
without PostgreSQL. The session is a recorder rather than a connection, so the
statements are the ones the repository actually builds rather than statements a
test rebuilt beside it.

Whether those statements return the rows the seed wrote is settled against a
live database by tests/integration/test_curriculum_api.py.
"""

import uuid

from sqlalchemy.dialects import postgresql

from app.infrastructure.persistence.curriculum import CurriculumVersion, LearningProgram
from app.infrastructure.persistence.curriculum_repository import SqlAlchemyCurriculumRepository

VERSION_ID = uuid.UUID("00000000-0000-0000-0000-0000000000ff")
PROGRAM_ID = uuid.UUID("00000000-0000-0000-0000-0000000000aa")


class RecordingSession:
    """Captures the statements a repository builds and returns nothing."""

    def __init__(self) -> None:
        self.statements = []
        self.gets = []

    def scalar(self, statement):
        self.statements.append(statement)
        return None

    def scalars(self, statement):
        self.statements.append(statement)
        return iter(())

    def get(self, model, identifier):
        self.gets.append((model, identifier))
        return None


def rendered(statement) -> str:
    """Render a statement as PostgreSQL SQL with its values inlined."""
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def repository() -> tuple[SqlAlchemyCurriculumRepository, RecordingSession]:
    session = RecordingSession()
    return SqlAlchemyCurriculumRepository(session), session


def test_listing_programs_orders_before_it_slices():
    """Slicing an unordered result would return a different page each request."""
    reader, session = repository()

    reader.list_learning_programs(limit=25, offset=50)

    sql = rendered(session.statements[0])
    assert "ORDER BY learning_programs.code" in sql
    assert sql.index("ORDER BY") < sql.index("LIMIT")
    assert "LIMIT 25" in sql
    assert "OFFSET 50" in sql


def test_counting_programs_ignores_any_page_window():
    reader, session = repository()

    reader.count_learning_programs()

    sql = rendered(session.statements[0])
    assert "count(*)" in sql
    assert "LIMIT" not in sql


def test_active_versions_are_fetched_for_every_program_in_one_statement():
    reader, session = repository()

    reader.list_active_curriculum_versions([PROGRAM_ID, VERSION_ID])

    sql = rendered(session.statements[0])
    assert "curriculum_versions.learning_program_id IN" in sql
    assert "curriculum_versions.status = 'active'" in sql


def test_active_versions_for_no_programs_issues_no_statement():
    reader, session = repository()

    assert reader.list_active_curriculum_versions([]) == ()
    assert session.statements == []


def test_reading_by_identifier_uses_the_primary_key_rather_than_a_scan():
    reader, session = repository()

    reader.find_learning_program(PROGRAM_ID)
    reader.find_curriculum_version(VERSION_ID)

    assert session.gets == [(LearningProgram, PROGRAM_ID), (CurriculumVersion, VERSION_ID)]


def test_listing_topics_reaches_the_version_through_its_subjects():
    reader, session = repository()

    reader.list_topics(VERSION_ID)

    sql = rendered(session.statements[0])
    assert "JOIN subjects ON topics.subject_id = subjects.id" in sql
    assert "WHERE subjects.curriculum_version_id" in sql


def test_listing_relationships_is_scoped_by_the_source_topic_version():
    reader, session = repository()

    reader.list_topic_relationships(VERSION_ID)

    sql = rendered(session.statements[0])
    assert "JOIN topics ON topic_relationships.source_topic_id = topics.id" in sql
    assert "JOIN subjects ON topics.subject_id = subjects.id" in sql
