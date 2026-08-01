---
title: LearnFlow Architecture Decision Register
status: approved
owner: architecture
last_updated: 2026-08-01
related:
  - ../00-project-context.md
  - ../adr/README.md
  - ../adr/ADR-000-template.md
---

# LearnFlow Architecture Decision Register

## Purpose

Provide a concise index of approved, durable LearnFlow decisions. This register is a navigation aid, not a replacement for detailed documents or Architecture Decision Records (ADRs).

When a decision is significant enough to affect multiple modules, future contributors, data, security, or deployment, create the linked ADR before implementing the affected area.

## Decision Statuses

- **Approved:** agreed direction; implementation may proceed when its detailed documentation is ready.
- **Accepted — ADR-NNN:** approved direction with an accepted ADR recording its rationale.
- **ADR pending:** approved direction that still requires a formal ADR before or alongside implementation.
- **ADR proposed — ADR-NNN:** approved direction whose ADR is drafted and awaiting project-owner acceptance.
- **Deferred:** intentionally not implemented now; revisit only when the stated trigger occurs.

These are register statuses. They are distinct from the document `status` field in front matter, which uses the vocabularies defined in [documentation standards](../development/documentation-standards.md).

## Approved Decisions

| ID | Decision | Status | Detail | ADR status |
| --- | --- | --- | --- | --- |
| DEC-001 | LearnFlow is a generic AI learning-mentor platform; GATE CSE is the first curated learning program. | Approved | [Vision](../vision/vision.md), [Domain model](../domain/domain-model.md) | Product decision; ADR optional |
| DEC-002 | The first release is a local-first, single-learner MVP. | Approved | [MVP scope](../requirements/mvp.md), [Non-functional requirements](../requirements/non-functional.md) | ADR pending if deployment boundary is formalized |
| DEC-003 | Curriculum, subjects, topics, and subtopics are data-driven; they are not hardcoded in frontend code. | Approved | [Functional requirements](../requirements/functional.md), [Domain model](../domain/domain-model.md) | Accepted — [ADR-012](../adr/ADR-012-curriculum-seed-and-reconciliation.md) |
| DEC-004 | The initial curriculum is a verified GATE CSE curriculum, transcribed from the official syllabus and traceable to it. Syllabus-PDF extraction is a future reviewed workflow, not an MVP feature. | Approved | [MVP scope](../requirements/mvp.md), [Domain model](../domain/domain-model.md), [Database migrations](../database/migrations.md) | Accepted — [ADR-012](../adr/ADR-012-curriculum-seed-and-reconciliation.md) |
| DEC-005 | LearnFlow uses Clean Architecture with domain, application, presentation, infrastructure, and composition-root boundaries. | Approved | [Clean Architecture](clean-architecture.md) | Accepted — [ADR-001](../adr/ADR-001-clean-architecture.md) |
| DEC-006 | External capabilities use provider interfaces/adapters where realistic replacement is expected. | Approved | [Provider pattern](provider-pattern.md) | Accepted — [ADR-002](../adr/ADR-002-provider-pattern.md) |
| DEC-007 | Python with FastAPI is the initial backend/API technology. | Approved | [Architecture overview](overview.md) | ADR pending |
| DEC-008 | Next.js with TypeScript is the initial web frontend technology. | Approved | [Architecture overview](overview.md) | ADR pending |
| DEC-009 | PostgreSQL stores structured transactional data; repositories isolate persistence implementation. | Approved | [Architecture overview](overview.md), [Provider pattern](provider-pattern.md) | Accepted — [ADR-003](../adr/ADR-003-postgresql-persistence.md) |
| DEC-010 | Local filesystem storage is the initial source-file storage implementation; cloud storage is a future adapter. | Approved | [Provider pattern](provider-pattern.md) | ADR pending |
| DEC-011 | Ollama is the initial local AI provider for both generation and embeddings; AI is used for reasoning/generation, not durable memory or direct state changes. | Approved | [Architecture overview](overview.md), [Provider pattern](provider-pattern.md) | Accepted — [ADR-004](../adr/ADR-004-ollama-local-ai-provider.md) |
| DEC-012 | ChromaDB is the initial vector-search implementation; embeddings and retrieval remain replaceable. | Approved | [Architecture overview](overview.md), [Provider pattern](provider-pattern.md) | ADR pending |
| DEC-013 | Docker Compose provides reproducible local development; Ollama initially runs on the host machine and is configured by endpoint. | Approved | [Architecture overview](overview.md) | Accepted — [ADR-005](../adr/ADR-005-docker-compose-local-development.md) |
| DEC-014 | Start with a predictable custom orchestrator for product learning responsibilities; evaluate an agent framework only when workflows justify it. | Approved | [Architecture overview](overview.md), [MVP scope](../requirements/mvp.md) | Accepted — [ADR-006](../adr/ADR-006-custom-agent-orchestration.md) |
| DEC-015 | Learner progress is evidence-based: material completion, learning stage, activities, quizzes, external tests, mistakes, and revisions remain separate signals. | Approved | [Functional requirements](../requirements/functional.md), [Domain model](../domain/domain-model.md) | ADR pending |
| DEC-016 | External test-series results are manually entered by the learner; there is no third-party platform scraping, login sharing, or direct integration in the MVP. | Approved | [Functional requirements](../requirements/functional.md) | ADR pending |
| DEC-017 | Documentation is a source of truth: major decisions require ADRs, and implementation changes update affected documents. | Approved | [Project context](../00-project-context.md), [Documentation standards](../development/documentation-standards.md) | Accepted — [ADR-007](../adr/ADR-007-documentation-and-adr-policy.md) |
| DEC-018 | A mistake record has exactly one discovery source — quiz-attempt answer, external test result, revision record, or study activity — modelled as named nullable foreign keys rather than a polymorphic source field. | Approved | [Domain model](../domain/domain-model.md), [Database schema](../database/schema.md) | Accepted — [ADR-008](../adr/ADR-008-assessment-and-mistake-evidence-model.md) |
| DEC-019 | A checkpoint quiz covers one or more topics through a `checkpoint_quiz_topics` join table; the application requires at least one linked topic. | Approved | [Domain entities](../domain/entities.md), [Database schema](../database/schema.md) | Accepted — [ADR-008](../adr/ADR-008-assessment-and-mistake-evidence-model.md) |
| DEC-020 | Topic performance evidence belongs only to an external test result; checkpoint quiz outcomes reach topic progress through quiz attempts and question topic links. | Approved | [Domain model](../domain/domain-model.md), [Domain entities](../domain/entities.md) | Accepted — [ADR-008](../adr/ADR-008-assessment-and-mistake-evidence-model.md) |
| DEC-021 | Monthly plans are an MVP planning type alongside roadmap, weekly, and daily plans. | Approved | [MVP scope](../requirements/mvp.md), [Functional requirements](../requirements/functional.md), [Database schema](../database/schema.md) | Product decision; ADR optional |
| DEC-022 | Configuration variables use three categories — core runtime (`APP_*`, `API_*`), capability (`<CAPABILITY>_PROVIDER` plus capability-level settings), and vendor (`<VENDOR>_<SETTING>`). `EMBEDDING_MODEL` is removed; `API_BASE_URL` is frontend configuration. `deployment/environments.md` is the authoritative catalogue, and configuration is validated before the application is created. | Approved | [Environments and configuration](../deployment/environments.md) | Accepted — [ADR-009](../adr/ADR-009-configuration-naming-and-validation.md) |
| DEC-023 | Changes reach `main` through a pull request. CI runs the checks enumerated in [CI/CD strategy](../deployment/ci-cd.md) on pull requests to `main` and pushes to `main`; each remaining check is added with the artifact it verifies. AI-assisted delivery follows one repeatable workflow that stops at an open pull request and never merges. | Approved | [CI/CD strategy](../deployment/ci-cd.md), [Git workflow](../development/git-workflow.md), [Engineering AI workflow](../ai/engineering-ai.md) | Accepted — [ADR-010](../adr/ADR-010-feature-delivery-workflow.md) |
| DEC-024 | PostgreSQL persistence uses synchronous SQLAlchemy with psycopg 3. The schema is migrated one area per milestone, starting with the curriculum tables; `schema.md` remains the approved target for every area it documents — six when this decision was recorded, seven since DEC-026 added the examination schedule. Controlled values are validated text guarded by a `CHECK` constraint, and one active curriculum version per program is enforced by a partial unique index. | Approved | [Database schema](../database/schema.md), [Database migrations](../database/migrations.md) | Accepted — [ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md) |
| DEC-025 | Curriculum is loaded from a versioned data file by an idempotent seed that matches every record on a database-enforced natural key, updates in place, and never deletes. A topic code is unique within its subject; a subject or topic dropped from the source keeps its row. | Approved | [Database migrations](../database/migrations.md), [Database schema](../database/schema.md) | Accepted — [ADR-012](../adr/ADR-012-curriculum-seed-and-reconciliation.md) |
| DEC-026 | An examination period is published reference data modelled as a dated window, never a single guessed date. An examination schedule belongs to a learning program and cycle, carries its source and a `provisional`/`confirmed` status, and is loaded by its own idempotent seed. A study goal references a schedule, a target date, or both, enforced by a `CHECK`. The default learner timezone is `APP_DEFAULT_TIMEZONE`, defaulting to `Asia/Kolkata`. | Approved | [Database schema](../database/schema.md), [Domain model](../domain/domain-model.md), [Terminology](../domain/terminology.md) | Accepted — [ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md) |

## Deferred Decisions

| Topic | Current position | Re-evaluate when |
| --- | --- | --- |
| Authentication and multiple accounts | Design learner-owned data with future identity support; do not implement public accounts in the MVP. | A second real learner needs independent local/cloud data. |
| Cloud AI providers | Keep AI provider abstraction; use Ollama initially. | Local model quality, cost, or hosting requirements justify another provider. |
| Azure Blob Storage / cloud storage | Keep storage-provider abstraction; use local filesystem initially. | Shared/cloud deployment or multi-machine synchronization is needed. |
| Alternative vector database | Keep retrieval provider abstraction; use ChromaDB initially. | Scale, filtering, operational, or cloud-search needs justify migration. |
| Agent framework such as LangGraph | Keep product responsibilities modular; use custom orchestration initially. | Workflows require stateful graphs, checkpoints, complex branching, or human approval flows. |
| Mobile application | Keep backend APIs client-agnostic; do not build mobile clients now. | The web MVP is stable and real learner usage warrants it. |
| Public cloud deployment | Use Docker Compose locally; do not host publicly now. | The product needs access beyond the learner's local machine. |
| Branch protection on `main` | Rely on the pull-request workflow and CI checks; do not configure repository branch-protection rules yet. Branch protection is a repository setting, not a repository file, so it is not part of any change under version control. | A second contributor gains write access, or a merge bypasses CI in practice. See [ADR-010](../adr/ADR-010-feature-delivery-workflow.md). |
| Automated syllabus extraction | Keep curriculum data model generic; do not auto-create curricula from PDFs now. | GATE CSE workflow is stable and a reviewed setup experience is designed. |

## Accepted ADRs

These ADRs are accepted and hold the durable rationale, alternatives, and consequences for the decisions above:

| ADR | Decision | Register entry |
| --- | --- | --- |
| [ADR-001](../adr/ADR-001-clean-architecture.md) | Adopt Clean Architecture | DEC-005 |
| [ADR-002](../adr/ADR-002-provider-pattern.md) | Use provider interfaces for external capabilities | DEC-006 |
| [ADR-003](../adr/ADR-003-postgresql-persistence.md) | Use PostgreSQL for structured persistence | DEC-009 |
| [ADR-004](../adr/ADR-004-ollama-local-ai-provider.md) | Use Ollama as the initial local AI provider | DEC-011 |
| [ADR-005](../adr/ADR-005-docker-compose-local-development.md) | Use Docker Compose for local development | DEC-013 |
| [ADR-006](../adr/ADR-006-custom-agent-orchestration.md) | Start with a custom product-agent orchestrator | DEC-014 |
| [ADR-007](../adr/ADR-007-documentation-and-adr-policy.md) | Use repository documentation and ADRs as shared project memory | DEC-017 |
| [ADR-008](../adr/ADR-008-assessment-and-mistake-evidence-model.md) | Model assessment topics and mistake evidence sources explicitly | DEC-018, DEC-019, DEC-020 |
| [ADR-009](../adr/ADR-009-configuration-naming-and-validation.md) | Name and validate configuration variables explicitly | DEC-022 |
| [ADR-010](../adr/ADR-010-feature-delivery-workflow.md) | Deliver features through pull requests with automated gates | DEC-023 |
| [ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md) | Implement PostgreSQL persistence synchronously and migrate per milestone | DEC-024 |
| [ADR-012](../adr/ADR-012-curriculum-seed-and-reconciliation.md) | Load curriculum as reconciled reference data from a versioned file | DEC-003, DEC-004, DEC-025 |
| [ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md) | Model an examination period as a published window of reference data | DEC-026 |

Decisions still marked **ADR pending** above have an approved direction but no formal ADR yet. Create the ADR before or alongside implementation of the affected area.

Additional ADRs should be added only for durable, consequential decisions. Avoid creating ADRs for routine file names, minor implementation details, or reversible experiments.

## Change Rule

When a decision in this register changes:

1. Update the detailed documentation that explains it.
2. Create a new ADR or mark the existing ADR as superseded when applicable.
3. Update this register with the new decision and links.
4. Do not silently change architecture through implementation alone.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR directory](../adr/)
- [Architecture overview](overview.md)
- [Provider pattern](provider-pattern.md)
- [Technology stack](../development/tech-stack.md)
