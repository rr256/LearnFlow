---
title: LearnFlow Delivery Milestones
status: approved
owner: product-and-architecture
last_updated: 2026-08-01
related:
  - ../00-project-context.md
  - roadmap.md
  - ../requirements/mvp.md
  - ../development/git-workflow.md
  - ../deployment/ci-cd.md
  - ../deployment/docker.md
  - ../database/migrations.md
  - ../database/schema.md
  - ../adr/ADR-011-sqlalchemy-persistence-implementation.md
  - ../adr/ADR-012-curriculum-seed-and-reconciliation.md
  - ../adr/ADR-013-examination-schedule-and-study-goal.md
---

# LearnFlow Delivery Milestones

## Purpose

Define reviewable delivery checkpoints for LearnFlow. A milestone is complete only when its outcome is demonstrated and its documentation is aligned—not merely when files have been created.

## Milestone 0 — Documentation Foundation

**Outcome:** the repository contains a coherent, approved handbook for the MVP.

### Definition of Done

- [x] `docs/00-project-context.md` is the mandatory project entry point and links resolve.
- [x] Vision, MVP, functional, and non-functional requirements are approved.
- [x] Domain model, entities, and terminology are approved.
- [x] Architecture overview, Clean Architecture, provider pattern, and dependency rules are approved.
- [x] Database, API, RAG, AI workflow, development, deployment, and roadmap documentation is present and cross-linked.
- [x] Architecture decision register reflects approved and deferred decisions.
- [x] Required ADRs are created or explicitly scheduled before related implementation begins.
- [x] No duplicate documentation folder remains as a competing source of truth.
- [x] Documentation changes are committed in a reviewable Git commit.

## Milestone 1 — Local Platform Foundation

**Outcome:** a new contributor can run the technical base locally and obtain curated GATE CSE curriculum data.

### Definition of Done

- [ ] Repository skeleton follows `docs/development/folder-structure.md`.
- [x] Backend starts through FastAPI application factory/composition root.
- [x] `GET /health` returns a safe readiness response.
- [ ] Docker Compose starts frontend, backend, PostgreSQL, and ChromaDB. The `backend` and `postgres` services are implemented (`compose.yaml`, `docker/backend.Dockerfile`), and CI validates the topology and builds the image on every pull request — first passing on pull request #7. The item remains open on two counts: `chromadb` and `frontend` join Compose with the code that consumes them, and no container has been started yet, so `docker compose up` serving `GET /health` against the `postgres` service is still unverified. See [Docker strategy](../deployment/docker.md).
- [x] Backend configuration is validated from environment variables. Now includes `DATABASE_URL`, which has no default and is required.
- [x] Alembic initializes and applies an initial migration to a fresh PostgreSQL database. `20260731_01_create_curriculum_tables` creates the curriculum area, `20260731_02_add_topic_code_unique_constraint` amends it, and `20260801_01_create_examination_schedule_and_learner_goal_tables` adds the examination schedule area and the first two learner-planning tables; the CI `database` job applies them to an empty PostgreSQL service container, compares the models against the result, exercises the constraints, and downgrades back to empty on every pull request. The remaining schema areas are migrated with the milestones that use them, per [ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md).
- [x] Curated GATE CSE curriculum seed/import is idempotent. `backend/scripts/seed_curriculum.py`
  loads the curated GATE CSE curriculum — 11 subjects and 65 topics and subtopics, transcribed from
  the official syllabus — matching every record on a natural key, writing only what differs, and
  never deleting. A repeat run writes nothing. Covered by
  unit tests against a fake and by integration tests that apply the seed twice to an ephemeral
  PostgreSQL database in the CI `database` job. See
  [the curriculum seed](../database/migrations.md#the-curriculum-seed) and
  [ADR-012](../adr/ADR-012-curriculum-seed-and-reconciliation.md).
- [ ] Curriculum API endpoints return data-driven program/subject/topic hierarchy.
- [ ] Setup instructions work from a clean local environment.
- [ ] Relevant tests/build checks pass.

## Milestone 2 — Learner Setup and Progress Baseline

**Outcome:** one learner can establish a GATE CSE goal and see meaningful topic progress.

Part of this milestone arrived early, in Milestone 1: `learners` and `study_goals` were created
alongside the examination schedule they reference, because a goal with nothing to aim at is not
persistable, and the schedule seed that fills it shipped with them. Those items are checked below
with their evidence. `availability_slots` deliberately stayed behind — it would fix the `day_of_week`
numbering convention that no requirement yet constrains, which is what
[ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md) exists to avoid.

### Definition of Done

- [x] Published examination schedule seed/import is idempotent.
  `backend/scripts/seed_examination_schedule.py` loads the GATE 2027 schedule — six dated periods
  across registration, late registration, three examination weekends, and the results announcement —
  from `gate_cse_examination_schedule.json`, matching every record on a natural key the database
  enforces, writing only what differs, and never deleting. A repeat run writes nothing. It refuses to
  run before the curriculum seed, naming the command to run first. The schedule keeps its official
  source, the date that source was read, and a `provisional`/`confirmed` status, so a date is never
  presented as settled while its source says it may change. Covered by unit tests against a fake and
  by integration tests that apply the seed twice to an ephemeral PostgreSQL database in the CI
  `database` job. See [the examination schedule seed](../database/migrations.md#the-examination-schedule-seed)
  and [ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md).
- [ ] Learner profile/local identity is initialized safely. The `learners` table and the command that
  creates the single local learner exist, ahead of this milestone; the safe-initialization question
  is settled when an API and a frontend can reach it.
- [ ] Learner can select active GATE CSE curriculum, target date, and weekly availability. The
  curriculum and examination goal halves are done: `python -m scripts.set_study_goal` binds the
  learner to the active curriculum version and the published GATE 2027 examination window, and
  `study_goals` persists it. Weekly availability remains, and needs `availability_slots` plus the
  `day_of_week` numbering convention that is still an open decision. The goal aims at an examination
  *window* rather than a guessed date; see
  [ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md).
- [ ] Learner can browse curriculum in the frontend without hardcoded topic data.
- [ ] Learner can record material status, learning stage, and study activity.
- [ ] Progress overview shows subject/topic progress and priority focus areas.
- [ ] Supportive learning-stage labels and next actions are used in UI.
- [ ] API, domain, persistence, and frontend tests cover core progress state transitions.
- [ ] Requirements/API/schema docs are updated to match implementation.

## Milestone 3 — Planning and Revision

**Outcome:** LearnFlow provides an actionable study timeline and adapts it to learner progress.

### Definition of Done

- [ ] Learner can generate roadmap, monthly, weekly, and daily plan views.
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
- [x] CI configuration runs the checks enumerated in [CI/CD strategy](../deployment/ci-cd.md) on pull requests and pushes to `main` (`.github/workflows/pull-request.yml`), covering documentation, lint, backend tests, database migrations, and the container build. The Python checks were verified locally when they were added; the container checks were verified in CI, where they first ran and passed on pull request #7; the database checks run only in CI, because that workstation has no PostgreSQL.
- [ ] CI also covers frontend checks, once that artifact exists.
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
- [CI/CD strategy](../deployment/ci-cd.md) — what CI verifies today and what remains pending
- [Docker strategy](../deployment/docker.md) — which Compose services exist today
- [Database migrations](../database/migrations.md) — the migrations applied so far and the seeds that fill them
- [Database schema](../database/schema.md) — which schema areas exist today
- [ADR-013: Model an examination period as a published window of reference data](../adr/ADR-013-examination-schedule-and-study-goal.md) — why part of Milestone 2's schema arrived in Milestone 1
- [Deferred ideas](future-ideas.md)
