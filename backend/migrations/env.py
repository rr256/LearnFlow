"""Alembic migration environment.

This module is migration tooling, not application code. It sits alongside the
composition root in what it is allowed to touch: it reads validated settings and
imports infrastructure metadata, and it holds no learning business rules.

Importing every model module is what populates ``Base.metadata``. A model that
is not imported here is invisible to autogenerate, which would silently omit its
table from a generated migration.
"""

from logging.config import fileConfig

from alembic import context

from app.composition.config import load_settings
from app.infrastructure.persistence import curriculum  # noqa: F401  -- registers models
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.engine import create_database_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Resolve the target database URL.

    An explicit ``sqlalchemy.url`` set by a caller wins, which is how the test
    suite points a migration run at an isolated test database. Otherwise the
    application's own validated configuration supplies it.
    """
    configured = config.get_main_option("sqlalchemy.url")
    if configured:
        return configured
    return str(load_settings().database_url)


def run_migrations_offline() -> None:
    """Emit SQL for the migrations without connecting to a database.

    Used to review generated DDL and to verify a migration script on a machine
    that has no PostgreSQL available.
    """
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply the migrations against a live database in one transaction."""
    engine = create_database_engine(_database_url())
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                # Report column-type drift between the models and the database,
                # which Alembic does not compare by default.
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
