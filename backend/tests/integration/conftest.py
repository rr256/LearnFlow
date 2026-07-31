"""Fixtures for tests that need a real PostgreSQL database.

These tests are skipped unless ``TEST_DATABASE_URL`` names a database that may
be created and dropped freely. Nothing here falls back to ``DATABASE_URL``:
that is the development database, and
docs/deployment/environments.md forbids running automated tests against it or
against any learner data.

Each test starts from an empty database, has the migrations applied to it, and
leaves it empty again, so no test can observe another's rows.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.infrastructure.persistence.engine import create_database_engine, create_session_factory

TEST_DATABASE_URL_VARIABLE = "TEST_DATABASE_URL"
BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def database_url() -> str:
    """The isolated test database, or skip when none is configured."""
    url = os.environ.get(TEST_DATABASE_URL_VARIABLE)
    if not url:
        pytest.skip(
            f"{TEST_DATABASE_URL_VARIABLE} is not set. Point it at a disposable "
            "PostgreSQL database to run the migration and schema tests."
        )
    return url


@pytest.fixture(scope="session")
def alembic_config(database_url: str) -> Config:
    """Alembic configuration aimed at the test database.

    ``sqlalchemy.url`` is set here rather than left to the application settings,
    which is the override ``migrations/env.py`` honours. Percent signs are
    doubled because Alembic stores options in a ConfigParser, where a bare ``%``
    starts an interpolation.
    """
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


@pytest.fixture
def migrated_database(alembic_config: Config, database_url: str) -> Iterator[Engine]:
    """Apply every migration, yield an engine, then return the database to empty.

    Downgrading in teardown doubles as continuous coverage of the downgrade
    path, which docs/database/migrations.md requires to be exercised while it is
    still safe to do so.
    """
    command.upgrade(alembic_config, "head")
    engine = create_database_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()
        command.downgrade(alembic_config, "base")


@pytest.fixture
def session(migrated_database: Engine) -> Iterator[Session]:
    """A session bound to the migrated test database."""
    factory = create_session_factory(migrated_database)
    with factory() as open_session:
        yield open_session
