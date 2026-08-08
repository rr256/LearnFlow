---
title: LearnFlow Project Context
status: approved
owner: project-governance
last_updated: 2026-08-08
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

- Stage: documentation and architecture foundation, plus a minimal FastAPI backend foundation, the curriculum and examination-schedule persistence schema, the curated data that fills both, the first read API over the curriculum, and a Next.js frontend that reads it, through which a learner can complete setup — a profile, an active learning program, a study goal, the weekly study time they have available, and how they want a plan built — see that setup back on the home screen, record a learning stage against a topic while browsing the curriculum, generate an initial study plan from all of it, and mark the work in that plan done.
- Implemented: a FastAPI application built through a composition-root application factory; validated startup configuration for `APP_ENV`, `APP_LOG_LEVEL`, `APP_DEFAULT_TIMEZONE`, `API_HOST`, `API_PORT`, and the required `DATABASE_URL`; `GET /health`, an operational endpoint served outside `/api/v1`; the curriculum read endpoints CUR-001 to CUR-003 under `/api/v1/curriculum`; EXM-001, which reads the published examination schedules as reference data and resolves no learner; the learner-owned setup endpoints LRN-001, LRN-002, and GOAL-001 to GOAL-004, whose contracts are fixed by [ADR-016](adr/ADR-016-learner-onboarding-api-contracts.md), and GOAL-005, which replaces a goal's weekly availability a week at a time and is fixed by [ADR-018](adr/ADR-018-weekly-availability-slots.md); the planning preferences GOAL-001 and GOAL-004 accept and every goal response carries — a preferred session length and a topic order, each optional and neither defaulted — fixed by [ADR-019](adr/ADR-019-study-goal-planning-preferences.md); the first learner topic progress, PRG-004 recording a learning stage against a trackable topic and PRG-002 reading back what was recorded, contracted by [ADR-017](adr/ADR-017-topic-progress-api-and-schema.md) — all with the `data` envelope, `limit`/`offset` pagination, and the documented error envelope and [error codes](api/conventions.md#error-codes) applied to every failure; a Next.js + TypeScript frontend serving a home screen that reads back the learner's saved setup — the profile, their active study goal or, failing that, their most recent one, the goal's examination cycle with its window and every published examination period, and the study week and planning preferences saved against it — alongside a curriculum view that offers a learning-stage control beside each trackable topic and the learner setup screen that writes the goal, the week, and the preferences, configured by `API_BASE_URL` and calling the API from its own server — including its writes, which go through a server action — so no API address reaches a browser and, for as long as that holds, the backend needs no CORS middleware, per [ADR-015](adr/ADR-015-frontend-foundation-and-server-rendered-api-access.md); backend and frontend container images with Docker Compose `frontend`, `backend`, and `postgres` services, the frontend serving its own static `/health` for its container health check so a probe never calls the API; SQLAlchemy models plus Alembic migrations creating the curriculum tables, the examination schedule tables, `learners` and `study_goals`, `learner_topic_progress`, and `availability_slots`, and adding the two planning-preference columns to `study_goals`; an idempotent seed that loads the curated GATE CSE curriculum, described in [database migrations](database/migrations.md#the-curriculum-seed); a second idempotent seed that loads the published GATE 2027 examination schedule, described in [the examination schedule seed](database/migrations.md#the-examination-schedule-seed); and a command that binds the local learner to that curriculum and examination goal. Study plans complete the picture: PLN-001 generates a `roadmap` over every trackable topic and a `weekly` plan over the coming seven days, deterministically and with no AI provider, from the goal's horizon, the saved availability, the planning preferences, and any recorded stages, superseding rather than deleting whatever it replaces; PLN-002 and PLN-003 read them back, and a `/plan` screen shows them with the reason for every item — contracted by [ADR-020](adr/ADR-020-initial-study-plan-generation.md), with migration `20260806_03` creating `study_plans` and `plan_items`, and the first module in `backend/app/domain/` holding the two rules that decide a plan. PLN-004 then lets the learner act on that plan: it marks one item `completed` and puts it back to `planned`, writing the `status` and `completed_at` columns `20260806_03` created ahead of it — so it needed **no migration** — and the `/plan` screen offers the control beside every item on both panels. Completing is reversible, it moves that item alone, and nothing is counted or re-planned around it. Contracted by [ADR-021](adr/ADR-021-plan-item-completion.md).
- Delivery: changes reach `main` through a pull request. GitHub Actions runs backend tests, Ruff lint and format checks, documentation validation, frontend lint/type/test/build checks, database migration checks, and container build validation on pull requests to `main` and pushes to `main`. See [CI/CD strategy](deployment/ci-cd.md) and [git workflow](development/git-workflow.md).
- Not implemented: AI and RAG, external integrations, authentication, and every learner feature beyond completing setup, reading it back on the home screen, browsing the curriculum, recording a learning stage against a topic, generating a study plan, and marking one of its items done. The frontend has no progress-overview, resource, mentor, or assessment screen; the stage controls sit inside the curriculum view rather than in a screen of their own. **All five of FR-002's acceptance criteria are now met in full**, the last by the plan [ADR-020](adr/ADR-020-initial-study-plan-generation.md) generates; [API endpoints](api/endpoints.md#fr-002-acceptance-criteria) carries the count and stays authoritative for it. Planning itself is only begun: a plan item can now be marked done and put back (PLN-004), but it cannot be skipped or postponed, a plan cannot be adapted after missed work (PLN-005), and nothing says whether the learner's week can reach their horizon — all of which belong to FR-004 and Milestone 3, along with monthly and daily plan views and revision entirely. Nothing still totals a week outside a plan, and no preference or topic is ranked or scored. Three of FR-005's six acceptance criteria are met — marking a topic with one of the five stages, updating it at any time, and showing an encouraging next action. The other three need material completion, study activity, and the remaining evidence kinds, none of which is stored: PRG-001, PRG-003, ACT-001, and ACT-002 therefore stay uncontracted, and `learner_topic_progress` is created without `material_status`, `material_completed_at`, or `last_studied_at`. Planning, study-activity, revision, resource, and assessment tables are migrated with the milestones that use them, per [ADR-011](adr/ADR-011-sqlalchemy-persistence-implementation.md). Compose covers the frontend, backend, and PostgreSQL — the `chromadb` service joins it with the code that consumes it, per [Docker strategy](deployment/docker.md). Infer no application behavior beyond the implemented items above.
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
| Frontend | [development/folder-structure.md](development/folder-structure.md), [development/coding-standards.md](development/coding-standards.md), [api/conventions.md](api/conventions.md), [deployment/environments.md](deployment/environments.md) |
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
- [ADR-015 — Build the frontend on Next.js and reach the API from the server](adr/ADR-015-frontend-foundation-and-server-rendered-api-access.md)
- [ADR-016 — Fix the learner setup API contracts](adr/ADR-016-learner-onboarding-api-contracts.md)
- [ADR-017 — Record manual topic progress as a learner-owned stage](adr/ADR-017-topic-progress-api-and-schema.md)
- [ADR-018 — Store weekly availability as named days replaced a week at a time](adr/ADR-018-weekly-availability-slots.md)
- [ADR-019 — Store planning preferences as typed columns replaced as a group](adr/ADR-019-study-goal-planning-preferences.md)
- [ADR-020 — Generate the initial study plan deterministically as a roadmap and a week](adr/ADR-020-initial-study-plan-generation.md)
- [ADR-021 — Mark a plan item completed as a reversible statement about work, not about the learner](adr/ADR-021-plan-item-completion.md)

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
