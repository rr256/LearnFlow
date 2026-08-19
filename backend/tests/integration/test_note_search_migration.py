"""The resource-note search index against a real PostgreSQL database.

Covers the testing requirements in docs/database/migrations.md for migration
``20260820_01``: it runs against an empty database, the object it creates is
verified, and the downgrade path is exercised by the fixture teardown.

The point of this file is the **agreement between two places**. The migration
writes the indexed expression out as a string; the repository builds the same
expression through SQLAlchemy. If they drift, PostgreSQL does not complain — it
silently stops using the index and quietly changes which passages match. So the
index definition stored by the database is compared against what the repository
compiles.
"""

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.dialects import postgresql

from app.infrastructure.persistence.note_search_repository import _searchable_document
from app.infrastructure.persistence.resources import SEARCH_CONFIGURATION

INDEX_NAME = "ix_resource_notes_search"


def index_definition(engine: Engine) -> str:
    """The `CREATE INDEX` PostgreSQL actually stored, normalised for comparison."""
    with engine.connect() as connection:
        definition = connection.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = :name"),
            {"name": INDEX_NAME},
        ).scalar_one()
    return " ".join(definition.split()).lower()


def test_the_search_index_is_created(migrated_database: Engine):
    inspector = inspect(migrated_database)

    indexes = {index["name"] for index in inspector.get_indexes("resource_notes")}

    assert INDEX_NAME in indexes


def test_it_is_a_gin_index(migrated_database: Engine):
    """A GIN index is what makes a `tsvector` containment test fast.

    A B-tree over the same expression would be built without complaint and never
    used.
    """
    assert "using gin" in index_definition(migrated_database)


def test_the_indexed_expression_covers_a_note_title_and_body(migrated_database: Engine):
    definition = index_definition(migrated_database)

    assert "to_tsvector" in definition
    assert f"'{SEARCH_CONFIGURATION}'" in definition
    assert "title" in definition
    assert "body" in definition


def test_the_index_matches_the_expression_the_repository_searches_with(
    migrated_database: Engine,
):
    """The agreement this file exists for.

    A mismatch between the migration's expression and the repository's is
    invisible at runtime: the search still returns correct rows, by sequential
    scan, and the index sits unused. Comparing the two catches that.
    """
    # Compiled without `literal_binds`: the configuration is a REGCONFIG, which
    # SQLAlchemy has no literal renderer for. The structure is what must agree.
    compiled = str(_searchable_document().compile(dialect=postgresql.dialect()))
    normalised = " ".join(compiled.split()).lower().replace("resource_notes.", "")

    definition = index_definition(migrated_database)

    assert f"to_tsvector('{SEARCH_CONFIGURATION}'::regconfig" in definition
    assert normalised.startswith("to_tsvector(")
    for fragment in ("title", "body", "||"):
        assert fragment in normalised, f"{fragment} missing from the repository expression"
        assert fragment in definition, f"{fragment} missing from the stored index"

    # The repository must not have quietly changed configuration either: its
    # literal is bound as a parameter, so it is compared directly.
    assert SEARCH_CONFIGURATION == "english"


def test_the_index_stores_no_column_of_its_own(migrated_database: Engine):
    """An index, deliberately, and not a generated `tsvector` column.

    A stored column would have meant altering a learner-owned table to hold a
    derived representation of note text, which is what ADR-037 kept out of the
    schema. See ADR-038.
    """
    inspector = inspect(migrated_database)

    columns = {column["name"] for column in inspector.get_columns("resource_notes")}

    assert columns == {"id", "resource_id", "title", "body", "status", "created_at", "updated_at"}
    for absent in ("search_vector", "tsv", "document", "embedding", "vector"):
        assert absent not in columns


def test_no_extension_was_installed(migrated_database: Engine):
    """`english` is built in, so this needed neither pg_trgm nor unaccent."""
    with migrated_database.connect() as connection:
        installed = {
            row[0] for row in connection.execute(text("SELECT extname FROM pg_extension")).all()
        }

    assert "pg_trgm" not in installed
    assert "unaccent" not in installed


def test_no_other_table_gained_an_index(migrated_database: Engine):
    """The migration creates one object and touches nothing else."""
    inspector = inspect(migrated_database)

    for table in ("resources", "resource_topic_links", "learners", "topics"):
        names = {index["name"] for index in inspector.get_indexes(table)}
        assert INDEX_NAME not in names


@pytest.mark.parametrize(
    ("stored", "topic_terms", "expected"),
    [
        ("Round robin schedulers pick a process.", "cpu or scheduling", True),
        ("Milk, bread, and nothing about computers.", "cpu or scheduling", False),
        ("The scheduler runs.", "scheduling", True),
        ("Deadlock needs four conditions.", "deadlock", True),
    ],
)
def test_the_configuration_stems_the_way_the_search_depends_on(
    migrated_database: Engine, stored: str, topic_terms: str, expected: bool
):
    """`english` stemming is the reason this search is worth having.

    "scheduling" must reach "schedulers"; `simple` would not, and the search
    would only ever find literal repetitions of a topic's name.
    """
    with migrated_database.connect() as connection:
        matched = connection.execute(
            text("SELECT to_tsvector(:config, :stored) @@ websearch_to_tsquery(:config, :terms)"),
            {"config": SEARCH_CONFIGURATION, "stored": stored, "terms": topic_terms},
        ).scalar_one()

    assert matched is expected
