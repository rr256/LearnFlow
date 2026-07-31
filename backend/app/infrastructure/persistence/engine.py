"""Database engine and session-factory construction.

Both functions are pure builders: they take the values they need and return a
configured object. Only the composition root calls them, because only the
composition root reads configuration.

Creating an engine opens no connection. SQLAlchemy connects lazily on first use,
so an unreachable database surfaces when a request or a migration actually needs
it rather than preventing the process from starting.
"""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_database_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Build the engine every repository will share.

    Args:
        database_url: A PostgreSQL URL including the driver, for example
            ``postgresql+psycopg://user:password@host:5432/database``.
        echo: Emit generated SQL to the logger. Development aid only -- it logs
            statement text, so it stays off unless a contributor opts in.

    Returns:
        An engine with connection pooling configured.
    """
    return create_engine(
        database_url,
        echo=echo,
        # A pooled connection can be closed by the server, a restarted container,
        # or a laptop resuming from sleep. Without this, the first request after
        # such a break fails on a dead connection instead of transparently
        # replacing it.
        pool_pre_ping=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build the factory that hands a unit of work to each repository call.

    ``expire_on_commit`` stays off so an entity remains readable after its
    transaction commits. Otherwise mapping a committed result to a response DTO
    would trigger a fresh SELECT per attribute against a finished transaction.
    """
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
