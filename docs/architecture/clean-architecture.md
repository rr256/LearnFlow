---
title: LearnFlow Clean Architecture
status: approved
owner: architecture
last_updated: 2026-07-28
related:
  - ../00-project-context.md
  - overview.md
  - dependency-rules.md
  - ../development/folder-structure.md
---

# LearnFlow Clean Architecture

## Purpose

Define how the LearnFlow backend separates durable learning rules from delivery mechanisms and external technologies.

The goal is not complexity for its own sake. The goal is to make learning behavior understandable, testable, and independent of whether the project uses Ollama or a cloud model, local files or Azure Blob Storage, ChromaDB or another vector database, and PostgreSQL or another supported relational database.

## Core Rule

Dependencies point inward toward business meaning.

```text
Presentation / Infrastructure
            ↓
        Application
            ↓
          Domain
```

The domain does not know about FastAPI, PostgreSQL, SQLAlchemy, Docker, ChromaDB, Ollama, filesystems, or frontend code.

## Layers

### 1. Domain Layer

The domain layer contains the stable concepts and rules of learning.

**Contains:**

- Entities and value objects: learner, topic, study goal, plan item, topic progress, revision record, quiz attempt, and test-performance evidence.
- Domain rules and invariants.
- Domain-level calculations that do not require external I/O.
- Domain exceptions that express business conditions.

**Examples:**

- A plan item being completed does not itself prove topic mastery.
- Topic-level test evidence cannot be inferred from only a total test score.
- A learning stage must lead to a supportive next action.

**Must not contain:**

- HTTP routes or request objects.
- ORM/database models or SQL queries.
- Calls to LLMs, embedding models, vector databases, storage SDKs, or web frameworks.
- Environment-variable access.

### 2. Application Layer

The application layer coordinates domain rules to complete a use case.

**Contains:**

- Use cases/services such as create study plan, record topic progress, ingest a resource, answer a mentor question, submit a quiz attempt, and record an external test result.
- Input/output data structures for use cases.
- Ports/interfaces for required external capabilities.
- Transaction boundaries and use-case-level authorization checks when applicable.
- Application error types.

**Examples of ports:**

- Curriculum repository
- Progress repository
- Study-plan repository
- Resource repository
- Storage provider
- Retrieval/vector-search provider
- Embedding provider
- AI provider
- Clock/ID generator, where needed for testability

**May depend on:** the domain layer and standard language features.

**Must not depend on:** FastAPI route handlers, SQLAlchemy/ORM models, specific database drivers, Ollama clients, ChromaDB clients, or file-storage SDKs.

### 3. Presentation Layer

The presentation layer exposes the application to an interface. The first interface is an HTTP API built with FastAPI.

**Contains:**

- API routes/controllers.
- HTTP request/response schemas.
- Request validation and serialization.
- Authentication/identity extraction once introduced.
- Mapping between HTTP data and application use-case inputs/outputs.
- HTTP error translation.

**May depend on:** application layer contracts and framework-specific code.

**Must not contain:** planning algorithms, direct database queries, direct provider calls, or domain rule duplication.

### 4. Infrastructure Layer

The infrastructure layer implements the application ports using specific technologies.

**Contains:**

- PostgreSQL/SQLAlchemy repositories and database mappings.
- Alembic migrations and database configuration.
- Local storage adapter and future Azure Blob Storage adapter.
- ChromaDB retrieval adapter and embedding adapters.
- Ollama AI adapter and future cloud AI adapters.
- PDF/text extraction and ingestion implementation.
- Logging, metrics, background-job mechanisms, and external client configuration.

**May depend on:** application-layer ports/contracts, domain types where needed for mapping, and technology libraries.

**Must not contain:** new learning rules that bypass application/domain behavior.

### 5. Composition Root

The composition root creates the running application by selecting and wiring concrete implementations.

**Responsibilities:**

- Read validated configuration.
- Choose the configured provider implementations.
- Construct repositories, storage, retrieval, AI adapters, and use cases.
- Register FastAPI routes and application dependencies.
- Configure logging and lifecycle handling.

This is the only place that should need to know that a particular deployment uses, for example, PostgreSQL + ChromaDB + local storage + Ollama.

## Dependency Direction

```text
FastAPI routes ──────────────► Application use cases ─────► Domain
SQLAlchemy repositories ─────► Application repository ports ─► Domain
Ollama adapter ──────────────► Application AI-provider port
ChromaDB adapter ────────────► Application retrieval-provider port
Local/Azure storage adapter ─► Application storage-provider port

Composition root ────────────► all layers, for wiring only
```

## Example: Grounded Mentor Question

```text
1. Presentation layer receives POST /mentor/questions.
2. It validates the request and calls the application use case.
3. The use case reads topic/progress context through repository ports.
4. The use case requests relevant sources through the retrieval port.
5. The use case asks the AI-provider port for an answer using selected context.
6. Infrastructure adapters perform the actual database, ChromaDB, and Ollama calls.
7. The application use case returns a mentor-response result.
8. Presentation maps it to an HTTP response.
```

No FastAPI route directly calls Ollama, and no Ollama adapter directly updates learner progress.

## Example: Record External Test Result

```text
1. Presentation validates learner-entered test data.
2. Application use case checks topic links and creates domain evidence.
3. Application persists the result and related topic evidence through repository ports.
4. Progress/revision use cases may derive future recommendations from the saved evidence.
5. Presentation returns the confirmed record and any relevant next action.
```

The MVP has no direct Testbook/Made Easy integration. An external test result is learner-entered evidence, not data pulled from another service.

## Data Models at Boundaries

Use different models for different responsibilities:

- **Domain entities:** express business meaning and invariants.
- **Application DTOs:** express use-case inputs and outputs.
- **API schemas:** express HTTP requests and responses.
- **Persistence models:** express database storage details.

Do not expose ORM models directly through APIs or make domain entities depend on database column shapes.

## Error Handling

- Domain errors describe invalid business states.
- Application errors describe use-case failures or unavailable dependencies.
- Presentation translates expected errors into consistent user-safe HTTP responses.
- Infrastructure errors are logged with safe diagnostic context and translated before leaking technology details outward.

## Testing Strategy by Layer

| Layer | Primary tests |
| --- | --- |
| Domain | Fast, deterministic unit tests for learning rules and invariants. |
| Application | Use-case tests with fake/mocked ports. |
| Infrastructure | Integration tests against PostgreSQL, storage, retrieval, and AI-adapter boundaries as appropriate. |
| Presentation | API contract and request-validation tests. |

## Pragmatic Constraint

The MVP should not create abstractions that have no expected use. Provider interfaces are justified because AI, storage, embeddings, and vector search are explicitly expected to evolve. Small internal utilities can remain simple until they have a real replacement or testing need.

## Related Documents

- [Project context](../00-project-context.md)
- [Architecture overview](overview.md)
- [Dependency rules](dependency-rules.md)
- [Provider pattern](provider-pattern.md)
- [Folder structure](../development/folder-structure.md)
- [Coding standards](../development/coding-standards.md)
