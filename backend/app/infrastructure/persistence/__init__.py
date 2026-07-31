"""PostgreSQL persistence: SQLAlchemy models and database/session setup.

This package is the only place in the backend that imports SQLAlchemy, apart
from the Alembic migration environment. Domain and application code must never
import an ORM model or a database session; see ADR-003 and
docs/architecture/dependency-rules.md.
"""
