---
title: LearnFlow Repository and Folder Structure
status: approved
owner: architecture-and-development
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - tech-stack.md
  - ../architecture/clean-architecture.md
  - ../architecture/dependency-rules.md
---

# LearnFlow Repository and Folder Structure

## Purpose

Define where source code, configuration, tests, documentation, containers, scripts, and generated/local data belong.

The structure reflects Clean Architecture without creating unnecessary folders before code requires them. Empty folders should not be committed merely to match this diagram.

## Target Repository Layout

```text
learnflow/
├── README.md
├── CLAUDE.md                    # Project instructions for implementation assistants
├── compose.yaml                 # Local Docker Compose entry point
├── .env.example                 # Safe configuration-variable template
├── .gitignore
├── docs/                        # Authoritative engineering documentation
├── backend/
│   ├── requirements.txt         # Initial Python dependency declaration
│   ├── app/
│   │   ├── domain/
│   │   ├── application/
│   │   │   ├── ports/
│   │   │   ├── use_cases/
│   │   │   └── dto/
│   │   ├── presentation/
│   │   │   └── api/
│   │   ├── infrastructure/
│   │   │   ├── persistence/
│   │   │   ├── providers/
│   │   │   ├── storage/
│   │   │   └── rag/
│   │   └── composition/
│   ├── migrations/              # Alembic configuration and revisions
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── api/
│   └── scripts/                 # Backend-only seed/import utilities
├── frontend/
│   ├── app/                     # Next.js routes/pages
│   ├── features/                # Learner-facing feature modules
│   ├── components/              # Reusable UI components
│   ├── lib/                     # API client and frontend-only utilities
│   ├── types/                   # Frontend types derived from API contracts
│   ├── tests/
│   └── public/
├── docker/
│   ├── backend.Dockerfile
│   └── frontend.Dockerfile
├── scripts/                     # Repository-level development utilities
└── .github/                     # Future CI/workflow configuration when introduced
```

## Root Files

| Path | Responsibility |
| --- | --- |
| `README.md` | Project introduction, quick start, and links to documentation. |
| `CLAUDE.md` | Concise repository instructions for Claude Code and compatible implementation assistants. It links to `docs/00-project-context.md`; it does not duplicate the handbook. |
| `compose.yaml` | Local service composition for frontend, backend, PostgreSQL, and ChromaDB. |
| `.env.example` | Safe environment-variable names/examples; no secrets. |
| `.gitignore` | Excludes virtual environments, node modules, local data, secrets, generated artifacts, and model/index data. |
| `docs/` | The authoritative project context, design, ADRs, and workflow documentation. |

## Backend Structure

### `backend/app/domain/`

Contains framework-independent learning concepts and rules.

Examples:

- Entities/value objects for topics, plans, progress, revisions, quizzes, and test evidence.
- Domain invariants and calculations.
- Domain exceptions.

Must not contain FastAPI, SQLAlchemy, provider SDKs, filesystem code, or environment configuration.

### `backend/app/application/`

Contains use cases and the ports they need.

| Subfolder | Responsibility |
| --- | --- |
| `ports/` | Repository/provider interfaces used by application services. |
| `use_cases/` | Feature workflows: create plan, record progress, ingest resource, mentor question, submit quiz, record test result. |
| `dto/` | Framework-independent input/output structures for use cases. |

Application code depends on domain concepts and ports, not on FastAPI or concrete providers.

### `backend/app/presentation/api/`

Contains FastAPI-specific delivery code.

Examples:

- Route modules.
- Request/response schemas.
- Dependency extraction for effective learner context.
- HTTP exception/error mapping.

Routes remain thin: validate, map, call a use case, map result to response.

### `backend/app/infrastructure/`

Contains concrete technology adapters.

| Subfolder | Responsibility |
| --- | --- |
| `persistence/` | SQLAlchemy models, repository implementations, database/session setup. |
| `providers/` | Ollama, embeddings, ChromaDB/retrieval adapters, future cloud adapters. |
| `storage/` | Local filesystem storage adapter and future cloud storage adapters. |
| `rag/` | PDF extraction, chunking, indexing, and retrieval implementation details. |

### `backend/app/composition/`

Contains application wiring only.

Examples:

- Validated configuration.
- Provider/repository construction.
- Dependency-injection setup.
- FastAPI application factory/lifecycle wiring.

Business rules do not belong here.

### `backend/migrations/`

Contains Alembic configuration and immutable migration revisions. Schema changes are documented in `docs/database/` and follow the migration workflow.

### `backend/tests/`

| Folder | Test focus |
| --- | --- |
| `unit/` | Domain and application behavior with no live external dependencies. |
| `integration/` | PostgreSQL, storage, provider-adapter, and RAG boundary tests. |
| `api/` | FastAPI request/response and contract tests. |

## Frontend Structure

### `frontend/app/`

Next.js routes/layouts only. It composes feature modules; it should not become the home for all UI business logic.

### `frontend/features/`

Feature-oriented modules, for example:

```text
onboarding/
curriculum/
planner/
progress/
revisions/
resources/
mentor/
quizzes/
external-tests/
```

Each feature owns its screens, view models, feature-specific components, and API interactions while using shared components/types where appropriate.

### `frontend/components/`

Reusable presentation components that are not specific to one learner workflow.

### `frontend/lib/`

Frontend-only utilities, including the typed API client, request/error helpers, formatting, and configuration access. It must not contain backend/domain rules.

### `frontend/types/`

TypeScript types based on public API contracts. Do not copy database/ORM types into the frontend.

## Docker and Scripts

### `docker/`

Contains Dockerfiles and small container build assets. Runtime configuration remains in `compose.yaml` and environment files.

### `scripts/`

Contains repository-level repeatable utilities, such as documentation validation, development setup checks, or release helpers. Scripts must be documented and must not contain personal paths/secrets.

### `backend/scripts/`

Contains backend/domain-specific utilities, such as idempotent GATE CSE curriculum seeding/import after that workflow is approved.

## Local and Generated Data

The following must stay outside Git or in ignored directories/volumes:

- Python virtual environments.
- `node_modules`.
- `.env` files with real values.
- PostgreSQL data volume.
- ChromaDB/vector-index data.
- Learner PDFs, notes, attachments, screenshots, and local storage contents.
- Downloaded Ollama models.
- Runtime logs containing private learner data.
- Generated build artifacts and coverage reports unless a tool explicitly requires otherwise.

Local data locations are configured through environment variables and Docker volumes; no source code may assume a developer-specific absolute path.

## Folder-Creation Rules

- Create a folder only when the first related file is added.
- Keep modules focused; do not create generic `utils`, `helpers`, or `common` folders as a dumping ground.
- Add a new cross-cutting folder only after documenting why existing boundaries do not fit.
- Mirror documentation terminology in code where practical: `study_plan`, `topic_progress`, `external_test_result`.

## Related Documents

- [Project context](../00-project-context.md)
- [Clean Architecture](../architecture/clean-architecture.md)
- [Dependency rules](../architecture/dependency-rules.md)
- [Technology stack](tech-stack.md)
- [Coding standards](coding-standards.md)
- [Docker strategy](../deployment/docker.md)
