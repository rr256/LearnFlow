---
title: LearnFlow Architecture Decision Register
status: approved
owner: architecture
last_updated: 2026-07-28
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
- **ADR pending:** approved direction that still requires a formal ADR before or alongside implementation.
- **Deferred:** intentionally not implemented now; revisit only when the stated trigger occurs.

## Approved Decisions

| ID | Decision | Status | Detail | ADR status |
| --- | --- | --- | --- | --- |
| DEC-001 | LearnFlow is a generic AI learning-mentor platform; GATE CSE is the first curated learning program. | Approved | [Vision](../vision/vision.md), [Domain model](../domain/domain-model.md) | Product decision; ADR optional |
| DEC-002 | The first release is a local-first, single-learner MVP. | Approved | [MVP scope](../requirements/mvp.md), [Non-functional requirements](../requirements/non-functional.md) | ADR pending if deployment boundary is formalized |
| DEC-003 | Curriculum, subjects, topics, and subtopics are data-driven; they are not hardcoded in frontend code. | Approved | [Functional requirements](../requirements/functional.md), [Domain model](../domain/domain-model.md) | ADR pending |
| DEC-004 | The initial curriculum is a verified GATE CSE curriculum. Syllabus-PDF extraction is a future reviewed workflow, not an MVP feature. | Approved | [MVP scope](../requirements/mvp.md), [Domain model](../domain/domain-model.md) | ADR pending |
| DEC-005 | LearnFlow uses Clean Architecture with domain, application, presentation, infrastructure, and composition-root boundaries. | Approved | [Clean Architecture](clean-architecture.md) | ADR required |
| DEC-006 | External capabilities use provider interfaces/adapters where realistic replacement is expected. | Approved | [Provider pattern](provider-pattern.md) | ADR required |
| DEC-007 | Python with FastAPI is the initial backend/API technology. | Approved | [Architecture overview](overview.md) | ADR pending |
| DEC-008 | Next.js with TypeScript is the initial web frontend technology. | Approved | [Architecture overview](overview.md) | ADR pending |
| DEC-009 | PostgreSQL stores structured transactional data; repositories isolate persistence implementation. | Approved | [Architecture overview](overview.md), [Provider pattern](provider-pattern.md) | ADR required |
| DEC-010 | Local filesystem storage is the initial source-file storage implementation; cloud storage is a future adapter. | Approved | [Provider pattern](provider-pattern.md) | ADR pending |
| DEC-011 | Ollama is the initial local AI provider; AI is used for reasoning/generation, not durable memory or direct state changes. | Approved | [Architecture overview](overview.md), [Provider pattern](provider-pattern.md) | ADR required |
| DEC-012 | ChromaDB is the initial vector-search implementation; embeddings and retrieval remain replaceable. | Approved | [Architecture overview](overview.md), [Provider pattern](provider-pattern.md) | ADR pending |
| DEC-013 | Docker Compose provides reproducible local development; Ollama initially runs on the host machine and is configured by endpoint. | Approved | [Architecture overview](overview.md) | ADR required |
| DEC-014 | Start with a predictable custom orchestrator for product learning responsibilities; evaluate an agent framework only when workflows justify it. | Approved | [Architecture overview](overview.md), [MVP scope](../requirements/mvp.md) | ADR required |
| DEC-015 | Learner progress is evidence-based: material completion, learning stage, activities, quizzes, external tests, mistakes, and revisions remain separate signals. | Approved | [Functional requirements](../requirements/functional.md), [Domain model](../domain/domain-model.md) | ADR pending |
| DEC-016 | External test-series results are manually entered by the learner; there is no third-party platform scraping, login sharing, or direct integration in the MVP. | Approved | [Functional requirements](../requirements/functional.md) | ADR pending |
| DEC-017 | Documentation is a source of truth: major decisions require ADRs, and implementation changes update affected documents. | Approved | [Project context](../00-project-context.md), [Documentation standards](../development/documentation-standards.md) | ADR required |

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
| Automated syllabus extraction | Keep curriculum data model generic; do not auto-create curricula from PDFs now. | GATE CSE workflow is stable and a reviewed setup experience is designed. |

## Required ADRs Before the Corresponding Implementation

Create these ADRs as the implementation phase reaches each decision:

1. `ADR-001-clean-architecture.md`
2. `ADR-002-provider-pattern.md`
3. `ADR-003-postgresql-persistence.md`
4. `ADR-004-ollama-local-ai-provider.md`
5. `ADR-005-docker-compose-local-development.md`
6. `ADR-006-custom-agent-orchestration.md`
7. `ADR-007-documentation-and-adr-policy.md`

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
