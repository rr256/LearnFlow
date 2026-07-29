---
title: LearnFlow Dependency Rules
status: approved
owner: architecture
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - clean-architecture.md
  - provider-pattern.md
  - ../development/coding-standards.md
---

# LearnFlow Dependency Rules

## Purpose

Make LearnFlow's Clean Architecture boundaries concrete enough for implementation, code review, testing, and AI-assisted changes.

## Rule Zero

Dependencies point inward toward stable learning concepts. Outer layers may depend on inner layers; inner layers must never depend on outer layers.

```text
Presentation ──────► Application ──────► Domain
Infrastructure ────► Application ──────► Domain
Composition Root ──► all layers, for wiring only
```

## Allowed Dependency Matrix

| From \ To | Domain | Application | Presentation | Infrastructure | Composition Root |
| --- | --- | --- | --- | --- | --- |
| **Domain** | Yes | No | No | No | No |
| **Application** | Yes | Yes | No | No | No |
| **Presentation** | Read-only types where necessary | Yes | Yes | No | No |
| **Infrastructure** | Mapping types where necessary | Yes | No | Yes | No |
| **Composition Root** | Yes | Yes | Yes | Yes | Yes |

“Yes” means a dependency is permitted, not automatically desirable. Keep imports narrow and responsibility-focused.

## Domain Rules

Domain code may depend only on:

- Other domain code.
- Standard-library capabilities that do not perform application I/O.
- Small, framework-independent utility libraries when justified and documented.

Domain code must not import or reference:

- FastAPI, Pydantic HTTP schemas, or web-framework objects.
- SQLAlchemy, Alembic, database sessions, SQL, or repository implementations.
- Ollama clients, cloud AI SDKs, ChromaDB, embedding libraries, or storage SDKs.
- Environment variables, configuration objects, Docker, filesystem paths, or HTTP clients.
- Frontend/UI code.

## Application Rules

Application code may depend on:

- Domain entities, value objects, and domain rules.
- Application-layer ports/interfaces, DTOs, and use cases.
- Framework-independent validation or utility libraries when justified.

Application code must not import or instantiate:

- FastAPI routes, request/response objects, or HTTP status types.
- SQLAlchemy sessions/models, raw SQL, Alembic migrations, or database drivers.
- Ollama/ChromaDB/vendor SDK clients.
- Local filesystem APIs or cloud-storage SDKs for provider work.
- Concrete adapters such as `OllamaProvider`, `ChromaRetrievalProvider`, or `PostgresStudyPlanRepository`.

Application services request outside work only through ports such as repositories, AI providers, retrieval providers, embedding providers, storage providers, clocks, and ID generators.

## Presentation Rules

The presentation layer may depend on:

- FastAPI and API-specific libraries.
- Application use cases and input/output DTOs.
- Authentication/identity extraction mechanisms when introduced.

The presentation layer must not:

- Query PostgreSQL or SQLAlchemy directly.
- Call Ollama, ChromaDB, storage, or embedding clients directly.
- Reimplement planning, revision, progress, or assessment rules.
- Return persistence/ORM models as public API responses.
- Decide provider selection.

Routes/controllers should validate, map, call a use case, and map the result/error back to HTTP.

## Infrastructure Rules

Infrastructure code may depend on:

- Application ports it implements.
- Domain types needed for correct mapping.
- Technology-specific libraries such as SQLAlchemy, Ollama clients, ChromaDB, file APIs, and cloud SDKs.

Infrastructure code must not:

- Make independent product decisions, such as how to prioritize revision or interpret learning stages.
- Import presentation routes/controllers.
- Expose provider-specific response types beyond the adapter boundary.
- Bypass application use cases to mutate learner-facing business state.

## Composition Root Rules

Only the composition root may:

- Read provider-selection configuration.
- Construct concrete adapters and repositories.
- Decide which implementation fulfils an application port.
- Wire dependencies into FastAPI application startup.

The composition root should contain wiring, not learning business logic.

## Frontend Rules

The frontend is a presentation client and must:

- Obtain curriculum, plans, progress, and resources through backend APIs.
- Treat backend/API data as the source of truth for subjects, topics, plan state, and progress.
- Keep presentation-specific state separate from durable learning state.

The frontend must not:

- Hardcode the GATE CSE curriculum as application truth.
- Directly access PostgreSQL, ChromaDB, Ollama, local storage, or provider credentials.
- Reimplement planning, revision scheduling, or learning-stage calculation.

## Data Boundary Rules

- Domain entities, API schemas, persistence models, and provider DTOs are distinct representations.
- Convert data explicitly at boundaries; do not let one layer's model leak into another by convenience.
- Do not expose absolute local storage paths or raw provider identifiers to the frontend unless a specific safe contract requires it.
- Keep source resources, derived embeddings/chunks, structured learner records, and generated AI content distinct.

## Mutation Rules

- Only application use cases may coordinate durable learner-facing state changes.
- AI-generated text is advisory input; it cannot silently update progress, learning stage, revision, or study plans.
- A database repository may persist approved domain/application changes, but it cannot independently derive new learning decisions.
- Background jobs follow the same application use cases and ports as synchronous requests.

## Testing Rules

- Domain tests do not start databases, web servers, or AI providers.
- Application tests use fakes/mocks for external ports.
- Infrastructure tests verify adapter behavior against the relevant technology boundary.
- API tests call the presentation layer with application dependencies supplied through the composition root or test overrides.

## Review Checklist

Before accepting a change, verify:

- [ ] No domain/application import depends on a technology-specific SDK.
- [ ] No API route performs direct persistence or AI-provider work.
- [ ] No provider adapter contains learner-planning or progress business rules.
- [ ] Data models are mapped at layer boundaries.
- [ ] New external capability uses a port/adapter when realistic replacement or testing requires it.
- [ ] Frontend changes do not duplicate backend curriculum or planning logic.

## Enforcement Approach

Initially, enforce these rules through repository structure, code review, tests, and AI-agent instructions. Add automated import-boundary checks once the backend package structure is established and the rules can be checked reliably.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-001: Adopt Clean Architecture](../adr/ADR-001-clean-architecture.md) — the decision these rules enforce
- [Clean Architecture](clean-architecture.md)
- [Provider pattern](provider-pattern.md)
- [Coding standards](../development/coding-standards.md)
- [Folder structure](../development/folder-structure.md)
