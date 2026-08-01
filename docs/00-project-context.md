---
title: LearnFlow Project Context
status: approved
owner: project-governance
last_updated: 2026-08-01
audience: all-contributors-and-ai-assistants
read_before: any-design-or-implementation-task
related:
  - README.md
  - development/documentation-standards.md
  - architecture/decisions.md
  - adr/README.md
---

# LearnFlow Project Context

## Purpose

This is the mandatory entry point for LearnFlow. It gives a human or AI assistant enough orientation to locate authoritative decisions without relying on chat history.

LearnFlow is an AI-powered, extensible learning platform. GATE Computer Science is its first learning program, not a hard-coded product boundary. The platform is intended to support structured learning journeys such as examinations, courses, certifications, and interview preparation.

## Current project state

- Stage: documentation and architecture foundation, plus a minimal FastAPI backend foundation, the curriculum and examination-schedule persistence schema, the curated data that fills both, the learner's study goal, and the first read API over the curriculum.
- Implemented: a FastAPI application built through a composition-root application factory; validated startup configuration for `APP_ENV`, `APP_LOG_LEVEL`, `APP_DEFAULT_TIMEZONE`, `API_HOST`, `API_PORT`, and the required `DATABASE_URL`; `GET /health`, an operational endpoint served outside `/api/v1`; the curriculum read endpoints CUR-001 to CUR-003 under `/api/v1/curriculum`, with the `data` envelope, `limit`/`offset` pagination, and the documented error envelope and [error codes](api/conventions.md#error-codes) applied to every failure; a backend container image with Docker Compose `backend` and `postgres` services; SQLAlchemy models plus Alembic migrations creating the curriculum tables, the examination schedule tables, and `learners` and `study_goals`; an idempotent seed that loads the curated GATE CSE curriculum, described in [database migrations](database/migrations.md#the-curriculum-seed); a second idempotent seed that loads the published GATE 2027 examination schedule, described in [the examination schedule seed](database/migrations.md#the-examination-schedule-seed); and a command that binds the local learner to that curriculum and examination goal.
- Delivery: changes reach `main` through a pull request. GitHub Actions runs backend tests, Ruff lint and format checks, documentation validation, database migration checks, and container build validation on pull requests to `main` and pushes to `main`. See [CI/CD strategy](deployment/ci-cd.md) and [git workflow](development/git-workflow.md).
- Not implemented: AI and RAG, the frontend, external integrations, and every learner feature beyond choosing a curriculum and an examination goal. The curriculum tables are the only ones an endpoint reads, and only for reading; no endpoint writes anything. The examination schedule and the study goal are still written and read only by the commands that maintain them — the learner and study-goal endpoints LRN-001, LRN-002, and GOAL-001 to GOAL-005 remain deferred by [ADR-013](adr/ADR-013-examination-schedule-and-study-goal.md) until the client that consumes them exists. `availability_slots`, planning, progress, resource, and assessment tables are migrated with the milestones that use them, per [ADR-011](adr/ADR-011-sqlalchemy-persistence-implementation.md). Compose covers the backend and PostgreSQL — the `chromadb` and `frontend` services join it with the code that consumes them, per [Docker strategy](deployment/docker.md). Infer no application behavior beyond the implemented items above.
- Decision status: use the documents in this repository and ADRs as the source of truth. Placeholders are intentionally not decisions.
- Immediate objective: implement approved Milestone 1 scope, replacing relevant placeholders with approved project decisions before implementing each affected area.

## Non-negotiable engineering direction

- Keep business rules independent from infrastructure.
- Use focused modules with clear responsibilities.
- Put external systems behind interfaces or adapters where replacement is realistic: AI providers, storage, vector search, embeddings, and persistence.
- Treat documentation and ADRs as part of the deliverable.
- Prefer simple, predictable workflows over premature autonomous or multi-agent complexity.

## Required reading by task

| If working on… | Read first |
| --- | --- |
| Product scope | [vision/vision.md](vision/vision.md), [requirements/mvp.md](requirements/mvp.md) |
| Architecture | [architecture/overview.md](architecture/overview.md), [architecture/dependency-rules.md](architecture/dependency-rules.md), relevant ADRs |
| Domain or database | [domain/domain-model.md](domain/domain-model.md), [database/schema.md](database/schema.md) |
| HTTP APIs | [api/conventions.md](api/conventions.md), [api/endpoints.md](api/endpoints.md) |
| RAG or AI | [rag/overview.md](rag/overview.md), [ai/learnflow-agents.md](ai/learnflow-agents.md) |
| Development practices | [development/tech-stack.md](development/tech-stack.md), [development/coding-standards.md](development/coding-standards.md) |
| Containers or release | [deployment/docker.md](deployment/docker.md), [deployment/environments.md](deployment/environments.md) |
| Delivery, CI, or assistant automation | [development/git-workflow.md](development/git-workflow.md), [deployment/ci-cd.md](deployment/ci-cd.md), [ai/engineering-ai.md](ai/engineering-ai.md) |

## Master index

### Product

- [Vision](vision/vision.md)
- [Functional requirements](requirements/functional.md)
- [Non-functional requirements](requirements/non-functional.md)
- [MVP scope](requirements/mvp.md)

### Decisions

- [Architecture decision register](architecture/decisions.md) — index of approved and deferred decisions
- [ADR directory](adr/README.md) — durable rationale for consequential decisions
- [ADR template](adr/ADR-000-template.md)

Accepted ADRs:

- [ADR-001 — Adopt Clean Architecture](adr/ADR-001-clean-architecture.md)
- [ADR-002 — Use provider interfaces for external capabilities](adr/ADR-002-provider-pattern.md)
- [ADR-003 — Use PostgreSQL for structured persistence](adr/ADR-003-postgresql-persistence.md)
- [ADR-004 — Use Ollama as the initial local AI provider](adr/ADR-004-ollama-local-ai-provider.md)
- [ADR-005 — Use Docker Compose for local development](adr/ADR-005-docker-compose-local-development.md)
- [ADR-006 — Start with a custom product-agent orchestrator](adr/ADR-006-custom-agent-orchestration.md)
- [ADR-007 — Use repository documentation and ADRs as shared project memory](adr/ADR-007-documentation-and-adr-policy.md)
- [ADR-008 — Model assessment topics and mistake evidence sources explicitly](adr/ADR-008-assessment-and-mistake-evidence-model.md)
- [ADR-009 — Name and validate configuration variables explicitly](adr/ADR-009-configuration-naming-and-validation.md)
- [ADR-010 — Deliver features through pull requests with automated gates](adr/ADR-010-feature-delivery-workflow.md)
- [ADR-011 — Implement PostgreSQL persistence synchronously and migrate per milestone](adr/ADR-011-sqlalchemy-persistence-implementation.md)
- [ADR-012 — Load curriculum as reconciled reference data from a versioned file](adr/ADR-012-curriculum-seed-and-reconciliation.md)
- [ADR-013 — Model an examination period as a published window of reference data](adr/ADR-013-examination-schedule-and-study-goal.md)
- [ADR-014 — Fix the public HTTP API response contract](adr/ADR-014-api-response-contract.md)

### Design and implementation

- [Architecture overview](architecture/overview.md)
- [Clean Architecture](architecture/clean-architecture.md)
- [Provider pattern](architecture/provider-pattern.md)
- [Dependency rules](architecture/dependency-rules.md)
- [Domain model](domain/domain-model.md)
- [Entities](domain/entities.md)
- [Terminology](domain/terminology.md)
- [Database overview](database/overview.md)
- [Schema](database/schema.md)
- [Migrations](database/migrations.md)
- [API conventions](api/conventions.md)
- [Endpoints](api/endpoints.md)
- [API versioning](api/versioning.md)
- [RAG overview](rag/overview.md)
- [Ingestion](rag/ingestion.md)
- [Retrieval](rag/retrieval.md)
- [Embeddings](rag/embeddings.md)
- [LearnFlow product agents](ai/learnflow-agents.md)
- [Engineering AI workflow](ai/engineering-ai.md)
- [AI prompts](ai/prompts.md)
- [Technology stack](development/tech-stack.md)
- [Folder structure](development/folder-structure.md)
- [Coding standards](development/coding-standards.md)
- [Git workflow](development/git-workflow.md)
- [Documentation standards](development/documentation-standards.md)
- [Docker](deployment/docker.md)
- [Environments](deployment/environments.md)
- [CI/CD](deployment/ci-cd.md)
- [Roadmap](roadmap/roadmap.md)
- [Milestones](roadmap/milestones.md)
- [Deferred ideas](roadmap/future-ideas.md)

## Workflow for AI assistants

1. Read this file and all documents named in the “Required reading by task” table.
2. Do not invent an architectural decision merely because a placeholder exists.
3. State conflicts, missing decisions, or broad scope changes before implementation.
4. Keep edits narrowly scoped to the assigned task.
5. Update linked documentation when implementation changes an approved behavior.
6. Do not overwrite a document marked `approved` without explicit direction and an ADR when needed.
7. For end-to-end delivery, follow the [engineering AI workflow](ai/engineering-ai.md). Its automated form stops for design decisions, opens a pull request, and never merges.

## Related Documents

- [Documentation home](README.md)
- [Documentation standards](development/documentation-standards.md)
- [Engineering AI workflow](ai/engineering-ai.md)
- [CI/CD strategy](deployment/ci-cd.md)
- [ADR template](adr/ADR-000-template.md)
