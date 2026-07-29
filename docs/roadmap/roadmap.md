---
title: LearnFlow Product Roadmap
status: approved
owner: product-and-architecture
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - milestones.md
  - future-ideas.md
  - ../requirements/mvp.md
---

# LearnFlow Product Roadmap

## Purpose

Sequence LearnFlow work into outcomes that support real GATE CSE study without allowing future ideas to overwhelm the local-first MVP.

This roadmap prioritizes a usable personal mentor over a feature-complete platform. Time estimates are intentionally omitted until implementation velocity and available study time are known.

## Product Sequence

```text
Documentation foundation
        ↓
Runnable local platform foundation
        ↓
Curated GATE CSE + learner setup + basic progress
        ↓
Planning and revision guidance
        ↓
Resources, RAG, and mentor assistance
        ↓
Quizzes and external-test evidence
        ↓
Hardening for daily personal use
        ↓
Future multi-user/cloud expansion only when justified
```

## Phase 0 — Architecture and Documentation Foundation

**Goal:** establish a durable source of truth before application implementation.

**Outcomes:**

- Documentation structure and master project context.
- Approved vision, requirements, domain model, architecture, database, API, RAG, AI workflow, and development standards.
- Architecture decision register and ADR workflow.
- Clear MVP boundaries and deferred-ideas process.

**Exit criteria:** an AI assistant or contributor can read the documentation and understand what to build, what not to build, and where to find detailed decisions.

## Phase 1 — Runnable Local Platform Foundation

**Goal:** create a reproducible local technical baseline.

**Outcomes:**

- Repository skeleton aligned with Clean Architecture.
- Docker Compose for frontend, backend, PostgreSQL, and ChromaDB.
- Host Ollama configuration and health checks.
- Backend configuration, logging, dependency wiring, API health endpoint.
- Alembic setup and initial database migration workflow.
- Curated GATE CSE seed-data workflow.

**Exit criteria:** a contributor can start the local environment, apply migrations, seed the GATE CSE curriculum, and read curriculum data through the API.

## Phase 2 — Learner Setup, Curriculum, and Progress Baseline

**Goal:** let one learner set a GATE CSE goal and track meaningful study progress.

**Outcomes:**

- Learner profile/local identity foundation.
- Study goal, target date, and availability setup.
- Data-driven curriculum explorer.
- Topic progress, supportive learning stages, and study-activity recording.
- Progress overview showing current state and priority focus areas.

**Exit criteria:** the learner can set up GATE CSE, browse the curriculum, record study work, and see non-judgmental progress by topic and subject.

## Phase 3 — Study Planning and Revision

**Goal:** make LearnFlow actively guide what to study next.

**Outcomes:**

- Roadmap, monthly, weekly, and daily plan generation.
- Plan-item completion/skip/postpone flow.
- Plan adaptation after missed work or changed availability.
- Revision scheduling, due list, and revision completion tracking.
- Clear next-action explanations and timeline trade-off visibility.

**Exit criteria:** the learner can receive and adjust an actionable study plan tied to target date, availability, progress, and revision needs.

## Phase 4 — Resources, RAG, and Mentor Assistance

**Goal:** make the mentor useful with the learner's own notes and PYQs.

**Outcomes:**

- Local resource registration and topic linking.
- PDF extraction, ingestion status, embeddings, and ChromaDB indexing.
- Grounded mentor questions using Ollama and retrieved resource excerpts.
- Learner-friendly source references and honest no-source/failure states.

**Exit criteria:** the learner can register GATE CSE notes, ask a topic question, and receive a grounded answer that identifies relevant source material.

## Phase 5 — Checkpoint Quizzes and External Test Evidence

**Goal:** use practice and test evidence to improve recommendations.

**Outcomes:**

- Topic-focused checkpoint quizzes.
- Quiz attempts, objective scoring, feedback, and mistake evidence.
- Manual entry of external test-series/mock results.
- Subject/topic performance evidence when available.
- Progress, revision, and plan recommendations informed by evidence.

**Exit criteria:** the learner can complete a checkpoint quiz or enter an external test result and see transparent, supportive next actions.

## Phase 6 — Daily-Use Hardening

**Goal:** make the local MVP dependable enough for regular study.

**Outcomes:**

- Automated tests for critical learning rules and API flows.
- Error handling, logs, health/readiness checks, backup/restore instructions.
- Improved UI states, accessibility basics, and performance feedback.
- CI verification for stable checks.
- README and setup guide validated on a clean machine where possible.

**Exit criteria:** the learner can use LearnFlow daily without fragile setup, unexplained failures, or risk of silent data loss.

## Phase 7 — Future Expansion

**Goal:** expand only after the local GATE CSE mentor is useful and validated.

Potential outcomes:

- Additional curated GATE branches and learning programs.
- Reviewed syllabus-PDF setup wizard.
- Multi-user accounts and secure data isolation.
- Cloud storage/synchronization and optional cloud AI providers.
- Hosted deployment, mobile clients, advanced analytics, and collaboration.
- More advanced orchestration only if concrete workflows require it.

## Prioritization Rule

Before starting a new feature, ask:

1. Does it help the learner plan, understand, practise, revise, or see progress now?
2. Is it required by the current phase’s exit criteria?
3. Does it introduce a new dependency, privacy risk, or architectural decision?
4. Should it instead be recorded in `future-ideas.md`?

If the answer to the first two questions is no, defer it.

## Related Documents

- [Project context](../00-project-context.md)
- [Milestones](milestones.md)
- [Deferred ideas](future-ideas.md)
- [MVP scope](../requirements/mvp.md)
- [Architecture decision register](../architecture/decisions.md)
