---
title: LearnFlow Delivery Milestones
status: approved
owner: product-and-architecture
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - roadmap.md
  - ../requirements/mvp.md
  - ../development/git-workflow.md
---

# LearnFlow Delivery Milestones

## Purpose

Define reviewable delivery checkpoints for LearnFlow. A milestone is complete only when its outcome is demonstrated and its documentation is aligned—not merely when files have been created.

## Milestone 0 — Documentation Foundation

**Outcome:** the repository contains a coherent, approved handbook for the MVP.

### Definition of Done

- [ ] `docs/00-project-context.md` is the mandatory project entry point and links resolve.
- [ ] Vision, MVP, functional, and non-functional requirements are approved.
- [ ] Domain model, entities, and terminology are approved.
- [ ] Architecture overview, Clean Architecture, provider pattern, and dependency rules are approved.
- [ ] Database, API, RAG, AI workflow, development, deployment, and roadmap documentation is present and cross-linked.
- [ ] Architecture decision register reflects approved and deferred decisions.
- [ ] Required ADRs are created or explicitly scheduled before related implementation begins.
- [ ] No duplicate documentation folder remains as a competing source of truth.
- [ ] Documentation changes are committed in a reviewable Git commit.

## Milestone 1 — Local Platform Foundation

**Outcome:** a new contributor can run the technical base locally and obtain curated GATE CSE curriculum data.

### Definition of Done

- [ ] Repository skeleton follows `docs/development/folder-structure.md`.
- [ ] Backend starts through FastAPI application factory/composition root.
- [ ] `GET /health` returns a safe readiness response.
- [ ] Docker Compose starts frontend, backend, PostgreSQL, and ChromaDB.
- [ ] Backend configuration is validated from environment variables.
- [ ] Alembic initializes and applies an initial migration to a fresh PostgreSQL database.
- [ ] Curated GATE CSE curriculum seed/import is idempotent.
- [ ] Curriculum API endpoints return data-driven program/subject/topic hierarchy.
- [ ] Setup instructions work from a clean local environment.
- [ ] Relevant tests/build checks pass.

## Milestone 2 — Learner Setup and Progress Baseline

**Outcome:** one learner can establish a GATE CSE goal and see meaningful topic progress.

### Definition of Done

- [ ] Learner profile/local identity is initialized safely.
- [ ] Learner can select active GATE CSE curriculum, target date, and weekly availability.
- [ ] Learner can browse curriculum in the frontend without hardcoded topic data.
- [ ] Learner can record material status, learning stage, and study activity.
- [ ] Progress overview shows subject/topic progress and priority focus areas.
- [ ] Supportive learning-stage labels and next actions are used in UI.
- [ ] API, domain, persistence, and frontend tests cover core progress state transitions.
- [ ] Requirements/API/schema docs are updated to match implementation.

## Milestone 3 — Planning and Revision

**Outcome:** LearnFlow provides an actionable study timeline and adapts it to learner progress.

### Definition of Done

- [ ] Learner can generate roadmap, weekly, and daily plan views.
- [ ] Plan items link to topics and supported actions.
- [ ] Learner can complete, skip, or postpone plan items.
- [ ] Learner can request plan adaptation after missed work or availability changes.
- [ ] Revision records are generated, listed, and updateable by learner action.
- [ ] Planning works with deterministic rules when Ollama is unavailable.
- [ ] Insufficient-time trade-offs are visible rather than hidden.
- [ ] Core planning/revision rules have deterministic tests.

## Milestone 4 — Resources, RAG, and Mentor

**Outcome:** learner-owned GATE CSE notes become usable, grounded mentor context.

### Definition of Done

- [ ] Learner can register/link supported local resources to topics.
- [ ] Supported text-based PDF can be extracted and indexed.
- [ ] Ingestion shows queued/processing/completed/failed status.
- [ ] Mentor retrieves authorized relevant excerpts before grounded answers.
- [ ] Mentor response shows useful source references when retrieval succeeds.
- [ ] No-source and provider-unavailable states are honest and understandable.
- [ ] Original files, resource metadata, and derived vectors are stored separately.
- [ ] Retrieval is tested with representative GATE CSE resources/queries.

## Milestone 5 — Quiz and External Test Evidence

**Outcome:** practice and learner-entered test results improve recommendations transparently.

### Definition of Done

- [ ] Learner can generate/select a topic checkpoint quiz.
- [ ] Learner can submit answers and receive objective scoring where supported.
- [ ] Quiz attempts, feedback, and mistakes are stored.
- [ ] Learner can manually enter external test result data and optional private reference attachment.
- [ ] Subject/topic evidence is recorded only when the learner/test report provides it.
- [ ] Progress/revision recommendations incorporate evidence without claiming permanent mastery.
- [ ] No external test-platform scraping, login sharing, or direct integration exists.
- [ ] Assessment flows have API/domain/persistence tests.

## Milestone 6 — Daily-Use Hardening

**Outcome:** the local mentor is dependable enough for regular personal study.

### Definition of Done

- [ ] Critical domain/application/API tests run reliably.
- [ ] Errors, logging, and health/readiness behavior are documented and tested where practical.
- [ ] Database/resource backup and restore instructions are documented.
- [ ] `.env.example`, `.gitignore`, Docker setup, and README are validated.
- [ ] CI runs stable checks for documentation, code, tests, and builds.
- [ ] Major learner workflows have loading, empty, error, and success states.
- [ ] Known limitations are documented rather than hidden.

## Milestone 7 — Expansion Readiness

**Outcome:** future expansion decisions are made from real usage evidence, not assumptions.

### Definition of Done

- [ ] Local GATE CSE workflow has been used long enough to identify genuine pain points.
- [ ] Deferred ideas are reviewed against usage evidence and roadmap priorities.
- [ ] Multi-user/cloud/mobile/other-program work has explicit requirements and ADRs before implementation.
- [ ] Any provider/storage/agent-framework change has a data migration and compatibility plan.

## Milestone Review Rules

- Review one milestone at a time; do not start a later milestone merely because it is interesting.
- A checklist item is complete only with evidence: working behavior, passing test, reviewed documentation, or demonstrated setup.
- If a new idea does not support the current milestone, add it to `future-ideas.md`.
- Commit milestone completion in a clear Git change and optionally tag a usable release.

## Related Documents

- [Project context](../00-project-context.md)
- [Roadmap](roadmap.md)
- [MVP scope](../requirements/mvp.md)
- [Git workflow](../development/git-workflow.md)
- [Deferred ideas](future-ideas.md)
