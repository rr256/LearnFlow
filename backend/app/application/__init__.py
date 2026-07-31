"""Application layer: use cases, the ports they need, and boundary DTOs.

Depends on domain concepts and ports only. It must never import FastAPI,
SQLAlchemy, a provider SDK, a filesystem API, or configuration; see
docs/architecture/dependency-rules.md.
"""
