---
title: "ADR-003: Use PostgreSQL for Structured Persistence"
status: accepted
owner: architecture-and-data
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - ../database/overview.md
  - ../database/schema.md
  - ../architecture/provider-pattern.md
---

# ADR-003: Use PostgreSQL for Structured Persistence

## Status

Accepted — 2026-07-29

## Context

LearnFlow needs durable, relational data for a learner's goals, curriculum, study plans, topic progress, revisions, resources, quiz attempts, mistakes, and manually entered external test results.

Although the initial MVP has one local learner, the intended product may later support friends and other learners. The user already has SQL experience and the local environment uses Docker Compose, so a production-capable relational database does not create an unreasonable setup burden.

## Decision

Use PostgreSQL as the initial structured transactional database.

Access PostgreSQL through SQLAlchemy-backed repository adapters that implement application repository ports. Use Alembic for versioned schema migrations.

PostgreSQL stores structured metadata and learner evidence. It is not the primary store for original PDFs/attachments or vector embeddings.

## Consequences

### Positive

- Strong relational constraints protect curriculum, learner ownership, plans, progress, and assessment data.
- Transactions support consistent multi-record updates.
- The model supports future multi-user use without redesigning from a local file/SQLite-only model.
- PostgreSQL works well through Docker Compose and aligns with existing SQL knowledge.
- JSONB remains available for carefully bounded flexible metadata without replacing core relational design.

### Negative

- Requires container/service setup compared with a single SQLite file.
- Requires migrations, backups, and schema discipline from the start.
- Moving to another relational database later remains a deliberate migration, even with repositories.

### Mitigations

- Docker Compose provides PostgreSQL without a native installation for contributors.
- Alembic and schema documentation make changes reviewable.
- Repository interfaces isolate application logic from SQLAlchemy/PostgreSQL details.
- Local backup/restore instructions are a required hardening milestone.

## Alternatives Considered

### SQLite for the MVP

**Rejected:** simple for one user, but less aligned with the planned relational complexity, future multi-user direction, and Docker-based project setup. The migration cost later is avoidable now.

### Microsoft SQL Server

**Rejected:** the developer has experience with it, but PostgreSQL has stronger default alignment with the selected open-source Python/Docker stack and easier cross-platform contributor setup for this project.

### NoSQL/Document Database

**Rejected:** core data is highly relational and requires constraints, transactions, and queryable relationships. Flexible provider/resource metadata can use bounded JSONB where necessary.

## Implementation Notes

- Follow `docs/database/overview.md`, `schema.md`, and `migrations.md`.
- Keep ORM models/repositories in infrastructure only.
- Associate learner-owned data with `learner_id` from the beginning.
- Use separate file storage for source resources and separate vector search for derived embeddings.
- Do not use direct ORM/database sessions in FastAPI routes or application use cases.

## Related Documents

- [Project context](../00-project-context.md)
- [Database overview](../database/overview.md)
- [Database schema](../database/schema.md)
- [Database migrations](../database/migrations.md)
- [Provider pattern](../architecture/provider-pattern.md)
- [Architecture decision register](../architecture/decisions.md)
