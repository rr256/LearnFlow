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
migrated one area per milestone; the curriculum tables, the examination schedule tables, and
`learners` and `study_goals` exist today. Curated content is loaded by idempotent seeds, not by
migrations — each matches records on a natural key and never deletes, so both are safe to repeat.
Run them in the order above; each refuses to run ahead of its predecessor. See
[`docs/database/migrations.md`](docs/database/migrations.md).

An examination is stored as a dated **window**, never as a single guessed date, and a published
schedule keeps its source and its `provisional`/`confirmed` status. See
[`docs/adr/ADR-013-examination-schedule-and-study-goal.md`](docs/adr/ADR-013-examination-schedule-and-study-goal.md).

Local containers — `compose.yaml` defines the `backend` and `postgres` services; ChromaDB and the
frontend join them with the code that uses them:

```bash
docker compose up --build                       # build and start
docker compose logs -f backend                  # follow logs
docker compose down                             # stop, preserving volumes
docker compose config -q                        # validate the topology
docker build -f docker/backend.Dockerfile .      # validate the image build
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
cd ..
python -m ruff check --config backend/pyproject.toml scripts/          # repository scripts lint
python -m ruff format --check --config backend/pyproject.toml scripts/ # repository scripts formatting
python scripts/validate_docs.py                                        # documentation front matter and links
```

CI runs these same checks on every pull request, except that the workflow runs `python -m pytest`
without `-W error`; see [`docs/deployment/ci-cd.md`](docs/deployment/ci-cd.md). Changes reach `main`
through a pull request, per
[`docs/development/git-workflow.md`](docs/development/git-workflow.md).

The database migration tests are outside this set because they need PostgreSQL. They skip unless
`TEST_DATABASE_URL` names a disposable database, and must never be pointed at `DATABASE_URL`. CI runs
them against an ephemeral service container.

## Never commit

Virtual environments, `node_modules`, real `.env` files, learner PDFs or notes, database volumes,
vector indexes, or secrets. See [`.gitignore`](.gitignore) and
[`docs/development/folder-structure.md`](docs/development/folder-structure.md).
