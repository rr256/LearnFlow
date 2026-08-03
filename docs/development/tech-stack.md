---
title: LearnFlow Technology Stack
status: approved
owner: architecture-and-development
last_updated: 2026-08-03
related:
  - ../00-project-context.md
  - ../architecture/overview.md
  - ../architecture/provider-pattern.md
  - ../deployment/docker.md
  - ../deployment/ci-cd.md
  - ../database/migrations.md
  - ../adr/ADR-011-sqlalchemy-persistence-implementation.md
---

# LearnFlow Technology Stack

## Purpose

Record the initial technologies selected for LearnFlow, the responsibility of each component, why it was chosen, and how it may evolve.

Versions are pinned in implementation dependency files after compatibility is tested. This document records architectural choices, not transient package-version numbers.

## Selected Stack

| Area | Initial technology | Responsibility | Why it fits | Replaceability |
| --- | --- | --- | --- | --- |
| Web frontend | Next.js + React + TypeScript | Learner-facing web application. | Mature web ecosystem, typed UI development, future deployment flexibility. | Client can evolve as long as API contracts remain stable. |
| Backend API | Python + FastAPI | HTTP API, application use cases, dependency wiring. | Strong AI/data ecosystem and clear typed API support. | Core backend choice; avoid replacing without a compelling reason. |
| Domain/application persistence | PostgreSQL | Structured curriculum, learner data, plans, progress, assessments, resource metadata. | Reliable relational data, constraints, transactions, and future multi-user support. | Repositories reduce coupling; migration remains consequential. |
| ORM / persistence mapping | SQLAlchemy | Maps infrastructure persistence models to PostgreSQL. | Mature Python ecosystem and supports repository implementation. | Implementation detail behind repositories. Used synchronously; see [ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md). |
| PostgreSQL driver | psycopg 3 | Connects SQLAlchemy and Alembic to PostgreSQL. | Current generation of the reference Python driver, and it serves both synchronous and asynchronous SQLAlchemy, so the execution model can change without changing driver. Installed as `psycopg[binary]`, which needs no local libpq or compiler. | Driver choice behind SQLAlchemy's dialect. |
| Database migrations | Alembic | Versioned PostgreSQL schema changes. | Standard SQLAlchemy migration workflow. | Expected to remain with SQLAlchemy unless persistence strategy changes. |
| Local AI generation | Ollama | Mentor explanations, grounded answers, and supported practice generation. | Local-first, low recurring cost, learner privacy. | Replaceable through `AIProvider` adapter. |
| Embeddings | Ollama embedding model | Converts resource chunks/queries to vectors. | Keeps the initial RAG workflow local and reuses the runtime already installed for generation. | Replaceable through `EmbeddingProvider`, independently of the generation provider. |
| Vector search | ChromaDB | Stores/searches derived embeddings and source metadata. | Suitable initial local RAG implementation. | Replaceable through `RetrievalProvider`. |
| Source-file storage | Local filesystem storage | Stores learner PDFs and private attachments. | Simple local-first setup. | Replaceable through `StorageProvider`; Azure Blob Storage is a future option. |
| Containers | Docker + Docker Compose | Reproducible local services and environment. | Lets contributors run the same backend/database/vector setup without separate database installation. | Deployment mechanism can evolve later. |
| Backend testing | Pytest | Domain, application, integration, and API tests. | Natural Python testing ecosystem. | Standard project tooling; exact plugins selected later. |
| Backend lint/format | Ruff | Linting, formatting, and import sorting for Python. | One fast tool replaces separate formatter, import sorter, and linter. | Tooling choice; reversible without affecting application code. |
| Backend configuration | pydantic-settings | Loads and validates environment configuration at startup. | Reuses the Pydantic validation already present through FastAPI; fails fast with field-level errors. | Confined to the composition root; see [ADR-009](../adr/ADR-009-configuration-naming-and-validation.md). |
| Frontend testing | Vitest + React Testing Library | Component and API-client verification. | Vitest reuses the bundler pipeline Next.js already implies, so tests need no second transform configuration; Testing Library queries by role and accessible name, which tests the markup a learner actually reaches. | Test-runner choice; reversible without affecting application code. |
| Frontend lint | ESLint with `eslint-config-next` | Linting for TypeScript, React, and Next.js, including the `jsx-a11y` accessibility rules. | Ships with the framework and needs no separate accessibility tooling to lint markup. | Tooling choice; reversible without affecting application code. |
| Frontend styling | CSS Modules | Component-scoped styles. | Built into Next.js, so styles stay beside their component with no styling dependency and no build-tool configuration. | Confined to component files; a styling framework remains addable later. |
| API documentation | FastAPI/OpenAPI output plus repository docs | Machine-readable API schemas and human architecture docs. | Keeps frontend contracts and documentation aligned. | API contract remains independent of documentation renderer. |
| Continuous integration | GitHub Actions | Runs the checks enumerated in [CI/CD strategy](../deployment/ci-cd.md) on pull requests and pushes to `main`. | Already hosted where the repository lives; needs no additional service or credential. | Workflow files are small and portable. |
| Documentation validation | PyYAML in `scripts/validate_docs.py` | Parses documentation front matter for the checks defined in [mechanical validation](documentation-standards.md#mechanical-validation). | A real YAML parser rejects malformed front matter that a hand-rolled subset parser would accept. | Development-only dependency; never enters the application runtime. See [ADR-010](../adr/ADR-010-feature-delivery-workflow.md). |

## Component Boundaries

```text
Next.js frontend
       ↓ REST /api/v1
FastAPI backend
       ↓ application ports
PostgreSQL | Local storage | ChromaDB | Ollama
```

The frontend does not directly access PostgreSQL, files, ChromaDB, Ollama, or provider credentials.

The backend business logic does not directly depend on provider SDKs. Concrete implementations are selected in the composition root.

## Local Runtime Direction

```text
Docker Compose
├── frontend service      implemented
├── backend service       implemented
├── PostgreSQL service    implemented
└── ChromaDB service      pending retrieval code

Host machine
└── Ollama service and downloaded models
```

The backend receives service endpoints and model names through environment configuration. Ollama remains on the host initially because local models can be large and are already installed on the learner's machine.

The frontend calls the backend from its own server, not from the browser. Learner-facing pages render as React Server Components, so the API address is server-side configuration that never reaches a client bundle, and the API needs no cross-origin allow-list. See [Docker strategy](../deployment/docker.md#the-frontend-service).

## Development Environment Requirements

Contributors need:

- Git.
- Docker Desktop / Docker Compose.
- Python 3.14 (the backend declares `requires-python = ">=3.14,<3.15"` in `backend/pyproject.toml`).
- Node.js 24 or later (the frontend declares `engines.node = ">=24.0.0"` in `frontend/package.json`; CI and the frontend image both use Node 24).
- Ollama plus configured models for RAG/mentor features.

PostgreSQL and ChromaDB should be supplied through Docker for normal local development. Contributors do not need separate native installations for them.

## Configuration Principles

- Use environment variables for endpoints, model names, database connection strings, storage locations, and secrets.
- Commit an `.env.example` with non-secret variable names and safe examples.
- Never commit real secrets, API keys, private learner files, databases, vector indexes, or local model files.
- Validate required configuration at application startup.
- Keep provider selection configuration in the composition root, not in domain/application logic.

## Deliberately Deferred Technology

| Capability | Current position | Trigger for adoption |
| --- | --- | --- |
| Cloud AI providers | Not required for MVP; Ollama is initial provider. | Local quality/capacity or hosted use requires it. |
| Azure Blob Storage | Not required for MVP; local storage is initial provider. | Multi-device/cloud deployment needs managed file storage. |
| Redis/Celery | Not required initially. | Ingestion/background work needs durable queues, retry management, or scale beyond simple application jobs. |
| Agent framework | Not required initially. | Product workflows need checkpoints, complex branching, or durable multi-step coordination. |
| Kubernetes | Not required. | Deployment scale/operational complexity justifies orchestration beyond Compose. |
| Public authentication provider | Not required for local single-learner MVP. | Multiple real users require login/account management. |
| Mobile application framework | Not required. | Web MVP is stable and mobile usage is validated. |

## Technology Selection Rules

Before adding a new dependency or service, confirm:

1. Which approved requirement it satisfies.
2. Why existing tools cannot meet the need.
3. Whether it affects privacy, cost, local portability, or architecture boundaries.
4. Whether it needs an ADR.
5. How it will be tested and configured.

Do not add a framework only because it is popular or because an AI assistant suggests it.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-002: Use provider interfaces for external capabilities](../adr/ADR-002-provider-pattern.md) — why these choices stay replaceable
- [ADR-004: Use Ollama as the initial local AI provider](../adr/ADR-004-ollama-local-ai-provider.md) — the generation and embedding choice
- [ADR-005: Use Docker Compose for local development](../adr/ADR-005-docker-compose-local-development.md) — the container choice
- [ADR-010: Deliver features through pull requests with automated gates](../adr/ADR-010-feature-delivery-workflow.md) — the CI and documentation-validation choices
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](../adr/ADR-011-sqlalchemy-persistence-implementation.md) — the driver and execution-model choices
- [Database migrations](../database/migrations.md) — the Alembic workflow
- [Architecture overview](../architecture/overview.md)
- [Provider pattern](../architecture/provider-pattern.md)
- [Docker strategy](../deployment/docker.md)
- [CI/CD strategy](../deployment/ci-cd.md)
- [Coding standards](coding-standards.md)
- [Engineering AI workflow](../ai/engineering-ai.md)
