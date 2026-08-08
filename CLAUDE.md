# LearnFlow — Instructions for AI Assistants

LearnFlow is an AI-powered, extensible learning platform. GATE Computer Science is its first
learning program, not a product boundary.

This file is a pointer, not a handbook. The authoritative documentation lives in [`docs/`](docs/).

## Read before any meaningful work

**Start with [`docs/00-project-context.md`](docs/00-project-context.md).** It is the mandatory
entry point and master index, and it names the task-specific documents to read next.

Do not propose or implement a change based on this file alone.

## Non-negotiable rules

**Architecture.** Follow Clean Architecture as defined in
[`docs/architecture/clean-architecture.md`](docs/architecture/clean-architecture.md) and
[`docs/architecture/dependency-rules.md`](docs/architecture/dependency-rules.md). Dependencies point
inward: domain and application code must never import FastAPI, SQLAlchemy, Ollama, ChromaDB,
filesystem APIs, or configuration. Only the composition root selects concrete implementations.

**Documentation.** Follow
[`docs/development/documentation-standards.md`](docs/development/documentation-standards.md).
Documentation is part of the deliverable: update affected documents in the same change as the code.
Consequential, hard-to-reverse decisions need an ADR in [`docs/adr/`](docs/adr/) and an entry in
[`docs/architecture/decisions.md`](docs/architecture/decisions.md).

**Terminology.** Use the canonical vocabulary in
[`docs/domain/terminology.md`](docs/domain/terminology.md) in code, APIs, database names, and UI
copy — including the terms it tells you to avoid.

**Scope.** Keep each change narrow and reviewable. No large unrelated refactors inside a feature
task. Follow [`docs/development/git-workflow.md`](docs/development/git-workflow.md) for branches and
commit messages.

## Before you change anything

1. State conflicts, missing decisions, or scope questions **before** implementing.
2. Do not invent an architectural decision because a placeholder exists — a placeholder is not a
   decision.
3. Do not overwrite a document marked `approved`, or an `accepted` ADR, without explicit direction.
4. Do not mark anything `approved` or `accepted` yourself.

## Backend quick reference

```bash
cd backend
python -m pip install -r requirements-dev.txt   # runtime + test/lint tooling
python -m app.main                              # serve on API_HOST / API_PORT
python -m uvicorn app.main:app --reload         # reload workflow (own --host/--port)
python -m alembic upgrade head                  # apply the database schema
python -m scripts.seed_curriculum               # load the curated curriculum, idempotently
python -m scripts.seed_examination_schedule     # load the published examination schedule
python -m scripts.set_study_goal                # bind the local learner to both
```

Tests, lint, and formatting are part of the repository check set below.

Database — PostgreSQL through SQLAlchemy and Alembic. `DATABASE_URL` is required and has no default.
Migrations are never applied automatically, by startup or by a container entrypoint. The schema is
migrated one area per milestone; the curriculum tables, the examination schedule tables, `learners`
and `study_goals` — including its two planning-preference columns — `learner_topic_progress`,
`availability_slots`, `study_plans`, and `plan_items` exist today, which completes the
learner-planning area. Curated content is loaded by idempotent seeds, not by
migrations — each matches records on a natural key and never deletes, so both are safe to repeat.
Run them in the order above; each refuses to run ahead of its predecessor. See
[`docs/database/migrations.md`](docs/database/migrations.md).

An examination is stored as a dated **window**, never as a single guessed date, and a published
schedule keeps its source and its `provisional`/`confirmed` status. See
[`docs/adr/ADR-013-examination-schedule-and-study-goal.md`](docs/adr/ADR-013-examination-schedule-and-study-goal.md).

The learner and study-goal endpoints are contracted by
[`docs/adr/ADR-016-learner-onboarding-api-contracts.md`](docs/adr/ADR-016-learner-onboarding-api-contracts.md),
weekly availability by
[`docs/adr/ADR-018-weekly-availability-slots.md`](docs/adr/ADR-018-weekly-availability-slots.md),
planning preferences by
[`docs/adr/ADR-019-study-goal-planning-preferences.md`](docs/adr/ADR-019-study-goal-planning-preferences.md),
the topic-progress endpoints by
[`docs/adr/ADR-017-topic-progress-api-and-schema.md`](docs/adr/ADR-017-topic-progress-api-and-schema.md),
study-plan generation by
[`docs/adr/ADR-020-initial-study-plan-generation.md`](docs/adr/ADR-020-initial-study-plan-generation.md),
and plan-item completion by
[`docs/adr/ADR-021-plan-item-completion.md`](docs/adr/ADR-021-plan-item-completion.md).
No request accepts a `learner_id`; the effective learner is resolved server-side.

A **learning stage** is stored and sent as `snake_case` — `not_explored`, `building_foundation`,
`developing_confidence`, `practice_ready`, `strong_understanding` — and rendered from the labels in
[`docs/domain/terminology.md`](docs/domain/terminology.md). A topic with no record has no stage and
reads as *Not explored*; nothing creates a record on a learner's behalf, and there is no way to clear
one. Only a topic with `is_trackable` may hold a stage.

A **day of the week** is stored and sent as its `snake_case` name — `monday` to `sunday` — never as an
index; there is deliberately no numbering convention, because Python, JavaScript, and PostgreSQL
disagree about which day is zero. **Weekly availability** belongs to a study goal and is replaced a
week at a time: the days GOAL-005 names become the week, a day left out is removed, and an empty list
clears it. Zero minutes is a day deliberately kept free, which is not the same as a day with no row.
Nothing totals a week — a plan places sessions on the days a week names and reports no total either.

A **planning preference** also belongs to a study goal, and is a session length
(`preferred_session_minutes`, 15 to 480) or a topic order (`topic_sequencing`, `syllabus_order` or
`prerequisites_first`). GOAL-001 and GOAL-004 accept them as one `planning_preferences` object and
every goal response carries it, always as an object whose members may be null. A supplied group
**replaces** the stored one, so a member left out of it is unset; omitting the field leaves the group
alone. A preference the learner has not set is `NULL`, never a default — nothing is invented on their
behalf. A session length is a duration, not a time of day. Nothing ranks or scores a preference.

A **study plan** is generated by PLN-001 from the goal, the curriculum, the saved week, the
preferences, and any recorded stages — **deterministically, with no AI provider**: the same inputs
produce the same plan. One generation writes a `roadmap` ordering every trackable topic across the
goal's horizon, and a `weekly` plan dating the first of them, when the learner's week has room. The
two rules that decide a plan — topic order and session placement — are pure functions in
`backend/app/domain/study_planning.py`, the only module in the domain layer. Generating again
**supersedes** the goal's active plans and keeps them; nothing is deleted, and a superseded plan reads
back exactly as written. An unset session length becomes 60 minutes *chosen by the planner and named
as its own* — nothing is stored against the goal. A recorded stage explains an item and never reorders
one; `priority` is an order, not a score; and nothing totals a day, a week, or a plan.
`prerequisites_first` currently yields syllabus order, because the curated curriculum stores no
prerequisite link, and the plan says so.

**PLN-004 marks one plan item completed and returns it to `planned`** — the first delivery against
FR-004. It accepts
`completed` and `planned` only, refusing `skipped` and `postponed` with a `422` because postponing
work has nowhere to move it to until PLN-005 exists. Completing is reversible and clears
`completed_at`, which is read from the server's clock rather than accepted from a caller. **Only the
named item moves**: no plan, no other item — including a roadmap item naming the same topic — and no
learning stage, because a plan item records whether planned work happened, not that a topic is
understood. Nothing is counted and nothing is re-planned. An item on a superseded plan is refused with
`409`. It needed **no migration**: `plan_items.status` and `completed_at` were created ahead of it.
PLN-005 — re-planning after missed work — is not implemented.

**Learner setup** is the canonical name for this capability — in prose, API documentation, and UI
copy. **Onboarding** names only the first-time UI flow, which is why `frontend/features/onboarding/`
keeps that name. See [`docs/domain/terminology.md`](docs/domain/terminology.md).

## Frontend quick reference

```bash
cd frontend
npm ci                                          # install the committed lockfile
npm run dev                                     # http://localhost:3000
```

Node.js 24 or later is required. Next.js + TypeScript, App Router, CSS Modules. The frontend calls the
API from its own server — learner-facing pages are React Server Components and writes go through a
server action, so the browser never reaches the backend, no CORS configuration exists, and
`API_BASE_URL` is server-side only. Today it serves a curriculum view over CUR-001 to CUR-003 that
also reads the learner's recorded stages over PRG-002 and writes one over PRG-004, a `/setup` screen
over EXM-001, LRN-001, LRN-002, and GOAL-001 to GOAL-005, a home screen at `/` that reads the
saved setup back over LRN-001, GOAL-002, and EXM-001, and a `/plan` screen that reads the current plan
over PLN-002 and PLN-003, generates one over PLN-001, and marks an item completed over PLN-004. A goal response carries the saved study week
and the saved planning preferences, so neither setup nor home calls anything extra to show them.

The frontend serves its own static `/health` for the container health check, distinct from the
backend's `GET /health`. It reaches nothing, so the probe asks only whether the frontend process is
responding rather than generating backend requests every interval.

A `"use server"` module may export only async functions. A constant exported from one fails at
runtime with a `500` that neither `tsc` nor `next build` reports; `frontend/tests/server-actions.test.ts`
checks the rule.

Local containers — `compose.yaml` defines the `frontend`, `backend`, and `postgres` services;
ChromaDB joins them with the code that uses it:

```bash
docker compose up --build                       # build and start
docker compose logs -f backend                  # follow logs
docker compose down                             # stop, preserving volumes
docker compose config -q                        # validate the topology
docker build -f docker/backend.Dockerfile .     # validate the backend image build
docker build -f docker/frontend.Dockerfile .    # validate the frontend image build
```

`docker compose down -v` deletes named volumes and is destructive — `postgres_data` holds learner
data; never present it as a routine stop command. See
[`docs/deployment/docker.md`](docs/deployment/docker.md).

Python 3.14 is required. `GET /health` is an operational endpoint served outside `/api/v1`.
Configuration is validated at startup; see
[`docs/deployment/environments.md`](docs/deployment/environments.md) for the variable catalogue.

## Repository checks

The canonical local check set is *Local Quality Checks* in
[`docs/development/coding-standards.md`](docs/development/coding-standards.md). Run all of it before
committing:

```bash
cd backend
python -m pytest -W error                                              # tests; warnings fail the run
python -m ruff check .                                                 # backend lint
python -m ruff format --check .                                        # backend formatting
cd ../frontend
npm ci                                                                 # install the committed lockfile
npm run lint                                                           # frontend lint
npm run typecheck                                                      # frontend types
npm test                                                               # frontend tests
npm run build                                                          # frontend production build
cd ..
python -m ruff check --config backend/pyproject.toml scripts/          # repository scripts lint
python -m ruff format --check --config backend/pyproject.toml scripts/ # repository scripts formatting
python scripts/validate_docs.py                                        # documentation front matter and links
```

CI runs these same checks on every pull request, except that the workflow runs `python -m pytest`
without `-W error`, and additionally builds both container images; see
[`docs/deployment/ci-cd.md`](docs/deployment/ci-cd.md). Changes reach `main`
through a pull request, per
[`docs/development/git-workflow.md`](docs/development/git-workflow.md).

The database migration tests are outside this set because they need PostgreSQL. They skip unless
`TEST_DATABASE_URL` names a disposable database, and must never be pointed at `DATABASE_URL`. CI runs
them against an ephemeral service container.

## Never commit

Virtual environments, `node_modules`, real `.env` files, learner PDFs or notes, database volumes,
vector indexes, or secrets. See [`.gitignore`](.gitignore) and
[`docs/development/folder-structure.md`](docs/development/folder-structure.md).
