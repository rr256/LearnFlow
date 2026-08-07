"""Framework-independent learning concepts and rules.

Nothing here imports FastAPI, SQLAlchemy, Pydantic, a provider SDK, the
filesystem, or configuration, and nothing here imports the application layer
either: dependencies point inward, so an application use case maps its records
onto these values rather than the other way round
(docs/architecture/dependency-rules.md).

This package exists from the change that first needed it, which is the
folder-creation rule in docs/development/folder-structure.md.
"""
