---
title: ADR-001: Adopt Clean Architecture
status: accepted
owner: architecture
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - ../architecture/clean-architecture.md
  - ../architecture/dependency-rules.md
---

# ADR-001: Adopt Clean Architecture

## Status

Accepted — 2026-07-29

## Context

LearnFlow combines long-lived learning rules with technologies that are expected to evolve: local AI through Ollama, local file storage, ChromaDB, PostgreSQL, future cloud providers, and potentially more client applications.

Without explicit boundaries, planning logic, learner-progress rules, and resource workflows would become coupled to FastAPI, ORM models, Ollama clients, or vector-database calls. Replacing a provider or testing critical rules would then require broad rewrites.

## Decision

Adopt Clean Architecture for the backend with these layers:

```text
Presentation / Infrastructure
            ↓
        Application
            ↓
          Domain
```

- **Domain:** learning concepts, invariants, and business rules.
- **Application:** use cases and interfaces/ports required to perform them.
- **Presentation:** FastAPI HTTP delivery, validation, and response mapping.
- **Infrastructure:** PostgreSQL repositories, storage adapters, RAG implementation, and AI/vector provider adapters.
- **Composition root:** configuration and dependency wiring only.

Dependencies point inward. Domain/application code cannot depend on FastAPI, SQLAlchemy, Ollama, ChromaDB, filesystem APIs, or cloud SDKs.

## Consequences

### Positive

- Learning behavior can be tested without live databases or models.
- AI/storage/vector/database providers can evolve behind explicit adapters.
- Frontend/API changes do not require changing domain rules.
- The codebase can support new learning programs and future clients without hardcoding GATE CSE logic into delivery layers.
- Architecture decisions are easier to review and explain.

### Negative

- Early implementation requires explicit DTO mapping, ports, and dependency wiring.
- Small features may touch more files than a direct framework-first implementation.
- Contributors and AI assistants must understand dependency rules before editing.

### Mitigations

- Keep abstractions focused on realistic replacement/testing needs.
- Use the repository folder structure and dependency rules to make boundaries obvious.
- Start with a small set of use cases and adapters; do not create empty layers or speculative interfaces.

## Alternatives Considered

### Framework-Centric Monolith

Put FastAPI routes, ORM queries, planning logic, and provider calls together.

**Rejected:** faster for a small demo, but too coupled for a product expected to support multiple providers, RAG, learning rules, and future users.

### Traditional Layered Architecture Without Strict Dependency Direction

Separate controllers/services/repositories but allow layers to import each other freely.

**Rejected:** provides organization but does not prevent business logic from depending on infrastructure.

### Microservices From the Start

Create independent services for planning, RAG, AI, and progress.

**Rejected:** operational and deployment complexity is not justified for a local-first MVP.

## Implementation Notes

- Follow `docs/architecture/clean-architecture.md` and `docs/architecture/dependency-rules.md`.
- Use application ports for repositories and provider capabilities.
- Keep FastAPI/SQLAlchemy/provider SDK code in presentation/infrastructure only.
- Add automated import-boundary checks after the backend package structure is in place.

## Related Documents

- [Project context](../00-project-context.md)
- [Clean Architecture](../architecture/clean-architecture.md)
- [Dependency rules](../architecture/dependency-rules.md)
- [Provider pattern](../architecture/provider-pattern.md)
- [Architecture decision register](../architecture/decisions.md)
