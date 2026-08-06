"""Tests over the SQL the migration chain renders, without a database.

Alembic can render a migration to SQL instead of executing it, so these run in
the unit suite for the reason tests/unit/test_curriculum_repository_sql.py does:
they compile DDL rather than applying it, and need no PostgreSQL.

They exist because of a specific mistake that reached CI. The `ck` naming
convention on `Base.metadata` interpolates the name an operation supplies, so
`op.drop_constraint("ck_study_goals_topic_sequencing_is_known", ...)` renders
`ck_study_goals_ck_study_goals_topic_sequencing_is_known` and fails against a
constraint that does not exist. Only a live database caught it, and only in a
fixture's teardown, where it surfaced as errors in every unrelated integration
test rather than as one clear failure.

A rendered-SQL test catches the same class of error in the change that introduces
it, on a workstation with no database.
"""

import io
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Offline rendering never opens a connection, so this names no real database.
OFFLINE_URL = "postgresql+psycopg://renderer@localhost/offline"


def rendered(direction: str, revisions: str) -> str:
    """The SQL one direction of the whole chain renders to, offline."""
    # `output_buffer` is where offline SQL goes; `stdout` only carries Alembic's
    # own progress messages, so capturing that one returns nothing.
    buffer = io.StringIO()
    config = Config(str(BACKEND_ROOT / "alembic.ini"), output_buffer=buffer, stdout=io.StringIO())
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", OFFLINE_URL)
    getattr(command, direction)(config, revisions, sql=True)
    return buffer.getvalue()


@pytest.fixture(scope="module")
def upgrade_sql() -> str:
    return rendered("upgrade", "base:head")


@pytest.fixture(scope="module")
def downgrade_sql() -> str:
    return rendered("downgrade", "head:base")


def constraint_names(sql: str) -> list[str]:
    """Every constraint name the SQL mentions, in either direction."""
    names = []
    for line in sql.splitlines():
        for keyword in ("ADD CONSTRAINT ", "DROP CONSTRAINT "):
            if keyword in line:
                names.append(line.split(keyword, 1)[1].split()[0].rstrip(";"))
    return names


@pytest.mark.parametrize("direction", ["upgrade_sql", "downgrade_sql"])
def test_no_constraint_name_repeats_its_convention_prefix(direction, request):
    """The mistake this module exists for: a name passed to an operation already
    carrying its `ck_<table>_` prefix is prefixed a second time."""
    doubled = [
        name
        for name in constraint_names(request.getfixturevalue(direction))
        if "_ck_" in name or "_uq_" in name or "_fk_" in name or "_pk_" in name
    ]

    assert doubled == []


@pytest.mark.parametrize("direction", ["upgrade_sql", "downgrade_sql"])
def test_every_constraint_name_fits_a_postgresql_identifier(direction, request):
    """PostgreSQL truncates past 63 characters, and a truncated name is one a
    downgrade cannot drop. `test_persistence_mapping.py` checks the models; this
    checks what the migrations actually emit, which is where a hand-written name
    can drift from them."""
    too_long = [
        name for name in constraint_names(request.getfixturevalue(direction)) if len(name) > 63
    ]

    assert too_long == []


def test_the_planning_preference_constraints_are_created_with_their_bounds(upgrade_sql):
    assert "ck_study_goals_preferred_session_minutes_within_bounds" in upgrade_sql
    assert "preferred_session_minutes >= 15" in upgrade_sql
    assert "preferred_session_minutes <= 480" in upgrade_sql
    assert "ck_study_goals_topic_sequencing_is_known" in upgrade_sql
    for choice in ("syllabus_order", "prerequisites_first"):
        assert f"'{choice}'" in upgrade_sql


def test_dropping_the_preference_columns_takes_their_checks_with_them(downgrade_sql):
    """PostgreSQL removes a constraint that depends on a dropped column, so the
    downgrade names neither check -- which is also what keeps it clear of the
    convention trap above."""
    assert "DROP COLUMN topic_sequencing" in downgrade_sql
    assert "DROP COLUMN preferred_session_minutes" in downgrade_sql
    assert "ck_study_goals_topic_sequencing_is_known" not in downgrade_sql
    assert "ck_study_goals_preferred_session_minutes_within_bounds" not in downgrade_sql


def test_the_chain_renders_in_both_directions(upgrade_sql, downgrade_sql):
    """A migration that cannot render offline cannot be reviewed as SQL either."""
    assert "CREATE TABLE learning_programs" in upgrade_sql
    assert "DROP TABLE learning_programs" in downgrade_sql
