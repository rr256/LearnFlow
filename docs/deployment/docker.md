---
title: LearnFlow Docker Strategy
status: approved
owner: development-and-operations
last_updated: 2026-08-01
related:
  - ../00-project-context.md
  - environments.md
  - ci-cd.md
  - ../development/tech-stack.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../database/migrations.md
  - ../database/schema.md
  - ../api/endpoints.md
---

# LearnFlow Docker Strategy

## Purpose

Define a reproducible local LearnFlow environment so the application, PostgreSQL, and ChromaDB can run consistently on another developer’s machine without separate native database setup.

## Initial Compose Topology

This is the approved target topology:

```text
compose.yaml
├── frontend      Next.js web application
├── backend       FastAPI API/application services
├── postgres      PostgreSQL structured persistence
└── chromadb      Derived vector-search storage

Host machine
└── ollama        Local AI/embedding runtime with downloaded models
```

Ollama runs on the host initially. The backend receives its endpoint and configured model names through environment variables.

## Implemented State

`compose.yaml` currently defines the `backend` and `postgres` services.

| Service | State |
| --- | --- |
| `backend` | Implemented — builds from `docker/backend.Dockerfile`; build verified in CI. |
| `postgres` | Implemented — `postgres:18-alpine` with a named volume and a `pg_isready` health check. |
| `chromadb` | Not implemented — no code reads `CHROMA_URL`. |
| `frontend` | Not implemented — no `frontend/` application exists. |

Each remaining service joins `compose.yaml` in the change that implements the code consuming it. This
follows the rule in [ADR-009](../adr/ADR-009-configuration-naming-and-validation.md) that a
configuration variable is added when its consumer exists. `postgres` joined when the backend gained a
configured engine and an Alembic environment that read `DATABASE_URL`; `chromadb` and `frontend` are
still waiting on theirs.

### The `postgres` service

| Decision | Value |
| --- | --- |
| Image | `postgres:18-alpine`, pinned to a major version so a rebuild cannot silently move the local database to a new major. The version floor is owned by [database schema](../database/schema.md), which requires PostgreSQL 15 or later. |
| Persistent data | The named volume `postgres_data`. |
| Health check | `pg_isready` against the configured user and database. |
| Published port | `127.0.0.1:5432` only, so the database is unreachable from other devices. It is published at all so a contributor can run Alembic and the integration tests from the host. |
| Credentials | `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`, each defaulting to `learnflow`. Local development values, not secrets. |

The `backend` service waits for `postgres` to report healthy. That is convenience, not necessity:
the backend creates its engine lazily and applies no schema at startup, so it boots whether or not
the database is reachable. Waiting means the first request meets a database ready to accept
connections.

Nothing in the Compose setup applies migrations. `docker compose up` starts services; schema changes
stay the explicit Alembic step described in [database migrations](../database/migrations.md).

**Migrations are applied from the host, not from the backend container.** The image copies
`backend/app` only, by the decision recorded above, so it contains neither `alembic.ini` nor
`migrations/`. The `postgres` service publishes 5432 on loopback precisely so a contributor can run
`python -m alembic upgrade head` and the integration tests against it. Contributors already need
Python 3.14 for the backend, per [technology stack](../development/tech-stack.md).

### Backend image and service decisions

| Decision | Value |
| --- | --- |
| Base image | `python:3.14-slim`, matching the Python version the backend requires. |
| Installed dependencies | `backend/requirements.txt` only. Test and lint tooling stays out of a runtime image. |
| Copied source | `backend/app` only — the Dockerfile copies nothing else, and `.dockerignore` keeps tests and tooling out of the build context as well. |
| Process user | A dedicated unprivileged `learnflow` user, not root. |
| Entry point | `python -m app.main`, the form that honours `API_HOST` and `API_PORT`. |
| Published port | Loopback only, so the API is not reachable from other devices on the local network. Both sides of the mapping follow `API_PORT`, which defaults to 8000. |
| Health check | `GET /health` probed with a standard-library `urllib` call, so the image needs no extra package. |

`.dockerignore` at the repository root keeps `.env` files, secrets, learner data, volumes, virtual
environments, documentation, and CI configuration out of every build context. No image contains a
`.env` file; Compose supplies configuration as environment variables.

### Verification status

**The build is verified in CI.** The `containers` job first ran on pull request #7 and passed:
`docker compose config -q` validated the topology and `docker build -f docker/backend.Dockerfile .`
built the image. It runs again on every pull request and every push to `main`, so a change that
breaks the build is caught there.

Two limits on what that proves:

- **No container has been started.** CI validates and builds; it does not run `docker compose up`.
  Neither health-check probe has therefore executed, no request has been served through a container,
  and the backend has never connected to the `postgres` service. Runtime behavior is unverified, as
  distinct from the build.
- **The commands were not run locally when this setup was prepared**, because Docker was not
  installed on that workstation. That was true again when the `postgres` service was added. CI is the
  authoritative verification. Container commands are deliberately outside the canonical
  [local quality checks](../development/coding-standards.md#local-quality-checks), which cover the
  checks needing nothing beyond Python; running them locally is optional and needs a Docker
  installation.

The migrations themselves are verified separately and more strongly: the CI `database` job applies
them to a real PostgreSQL service container on every pull request. That job uses a GitHub Actions
service rather than Compose, so it exercises the schema without exercising this topology.

The Milestone 1 Compose item stays unticked for both of the reasons above and because the topology
covers four services, two of which now exist; [milestones](../roadmap/milestones.md) records why.

## Service Responsibilities

| Service | Responsibility | Persistent data |
| --- | --- | --- |
| `frontend` | Learner-facing Next.js application. | None in normal runtime. |
| `backend` | FastAPI routes, application use cases, provider wiring, ingestion coordination. | May use configured local resource-storage mount in development. |
| `postgres` | Curriculum, learners, goals, plans, progress, assessments, resource metadata. | Named PostgreSQL volume. |
| `chromadb` | Derived chunks/vectors and retrieval metadata. | Named ChromaDB volume. |
| Host `ollama` | Local generation and embedding models. | Managed by host Ollama installation. |

## Networking

- Compose services communicate over the internal Compose network using service names, such as `postgres` and `chromadb`.
- The frontend communicates with the backend through configured API base URL; browser-visible values must not expose database/provider credentials.
- On Docker Desktop, the backend may reach host Ollama through a configurable host endpoint such as `host.docker.internal`. Do not hardcode it in application logic.
- Expose only the ports needed for local development; production exposure is a later concern.

## Persistent Data

Use named volumes or configured local mounts for durable runtime data:

```text
postgres_data    PostgreSQL database files
chroma_data      ChromaDB/vector index files
resource_storage Learner-owned PDFs and attachments, if stored through a container mount
```

Rules:

- Persistent data is outside Git and excluded by `.gitignore`.
- Learner resources and database volumes are private local data.
- Back up PostgreSQL and learner resource storage before destructive environment cleanup.
- ChromaDB data is derived and rebuildable, but backing it up may speed local recovery.

## Configuration

Use `.env` for local values and commit only `.env.example`.

[Environments and configuration](environments.md) is the authoritative catalogue of every LearnFlow
configuration variable, including which are implemented and which are planned. It is not duplicated
here, so the two documents cannot drift apart.

Variable naming follows the three categories defined in
[ADR-009](../adr/ADR-009-configuration-naming-and-validation.md): core runtime (`APP_*`, `API_*`),
capability (`<CAPABILITY>_PROVIDER` and capability-level settings), and vendor
(`<VENDOR>_<SETTING>`). All values are validated at backend startup.

Compose supplies these variables to the backend service, and to the frontend service once it exists.
When a container serves the
backend through `python -m app.main`, `API_HOST` must be `0.0.0.0` rather than the local default of
`127.0.0.1`, or the service will not accept connections from outside the container. A container that
invokes uvicorn directly must pass `--host 0.0.0.0` instead, because that form does not read
`API_HOST`.

`compose.yaml` therefore sets `API_HOST: 0.0.0.0` as a fixed value rather than interpolating it, so a
developer's local `API_HOST=127.0.0.1` cannot reach the container and leave the service unreachable.
`APP_ENV`, `APP_LOG_LEVEL`, and `API_PORT` do interpolate from the shell or a local `.env` file, with
the documented defaults applied when unset.

`DATABASE_URL` is fixed in the same way and for the same reason. A developer's `.env` names
`127.0.0.1` so host-side Alembic runs reach the published port; inside the container that address is
the container itself. Compose therefore composes the backend's URL from the `POSTGRES_*` values and
the `postgres` service name, so the two services cannot drift apart while the credentials stay in
one place.

## Local Development Commands

[README.md](../../README.md) documents the local container workflow. The commands are:

```bash
# Build/start local services
docker compose up --build

# Start in the background
docker compose up --build -d

# Start only the database, for host-side Alembic or test runs
docker compose up -d postgres

# View service logs
docker compose logs -f backend

# Stop services while preserving persistent data
docker compose down
```

Use `docker compose down -v` only with explicit care: it removes named volumes and can delete local PostgreSQL/ChromaDB data. It must never be presented as a routine stop command.

## Startup and Health Checks

- PostgreSQL and ChromaDB should define health checks before the backend treats them as ready.
- The backend should expose a safe health/readiness endpoint.
- Backend readiness must validate required configuration and connectivity to essential local services.
- Ollama/model availability should be reported separately and clearly; the rest of the app can remain available if AI generation is unavailable.
- The frontend should display understandable dependency-unavailable states rather than generic failures.

## Resource Storage in Local Development

- Store learner resources only in a configured application storage location, not arbitrary host paths.
- Use an opaque storage key in PostgreSQL; do not return raw mounted-container or host paths to the frontend.
- If a host bind mount is used during development, document the configured root and ensure it stays outside committed source folders.
- The storage-provider interface keeps a later Azure Blob Storage adapter possible.

## Images and Builds

- Backend image builds from `docker/backend.Dockerfile`. Implemented.
- Frontend image builds from `docker/frontend.Dockerfile`. Added with the frontend application.
- Use `.dockerignore` to exclude virtual environments, node modules, Git metadata where unnecessary, learner data, secrets, and build artifacts.
- Keep image build stages reproducible; do not rely on untracked local files.
- The build context is the repository root, so a Dockerfile can copy from `backend/`.
- CI validates the Compose topology and builds the backend image on every pull request; see
  [CI/CD strategy](ci-cd.md). No image is pushed to a registry.

## Database and Seed Workflow

On a new local environment:

1. Start Compose services — `docker compose up --build`.
2. Apply Alembic migrations from the backend workflow — `cd backend && python -m alembic upgrade head`.
3. Load the curated GATE CSE curriculum — `cd backend && python -m scripts.seed_curriculum`. It is
   safe to repeat; see [the curriculum seed](../database/migrations.md#the-curriculum-seed).
4. Load the published GATE 2027 examination schedule — `python -m scripts.seed_examination_schedule`.
   Also safe to repeat, and it refuses to run before step 3; see
   [the examination schedule seed](../database/migrations.md#the-examination-schedule-seed).
5. Bind the local learner to both — `python -m scripts.set_study_goal`. See
   [setting the local learner's study goal](../database/migrations.md#setting-the-local-learners-study-goal).
6. Confirm backend health and the curriculum-read endpoints — `GET /health`, then
   `GET /api/v1/curriculum/programs`, which returns the program step 3 loaded. See
   [API endpoints](../api/endpoints.md#curriculum-endpoints).

All six steps work today. The application must not silently create schema changes at startup outside
the Alembic migration workflow, so step 2 is never automatic; steps 3 to 5 are likewise always
explicit, and each refuses to run ahead of its predecessor.
[Database migrations](../database/migrations.md#environment-workflow) owns this sequence in full.

## Security and Privacy Rules

- Never commit `.env`, actual passwords, API keys, learner PDFs, screenshots, or runtime volumes.
- Do not publish database, ChromaDB, or storage ports unnecessarily outside local development.
- Do not mount broad host directories or the user home directory into containers.
- Keep Ollama/provider endpoints configurable and avoid sending learner resources outside the approved provider path.

## Future Evolution

- Containerized Ollama can be evaluated later if model/runtime management requires it.
- Cloud deployment will use separate environment/deployment documentation.
- Compose may remain useful for development even if a future hosted environment uses managed services.
- Redis/Celery or similar background-job infrastructure is deferred until ingestion/retry needs exceed simple application-managed jobs.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-005: Use Docker Compose for local development](../adr/ADR-005-docker-compose-local-development.md) — the decision this document implements
- [ADR-009: Name and validate configuration variables explicitly](../adr/ADR-009-configuration-naming-and-validation.md) — the variable naming categories Compose supplies
- [ADR-004: Use Ollama as the initial local AI provider](../adr/ADR-004-ollama-local-ai-provider.md) — why Ollama stays on the host rather than in Compose
- [Environments](environments.md)
- [CI/CD strategy](ci-cd.md) — the container checks that run on every pull request
- [Repository and folder structure](../development/folder-structure.md) — where `compose.yaml`, `docker/`, and `.dockerignore` live
- [Milestones](../roadmap/milestones.md) — why the Milestone 1 Compose item is still open
- [Technology stack](../development/tech-stack.md)
- [API endpoints](../api/endpoints.md) — the endpoints step 6 of the local workflow confirms
- [Database migrations](../database/migrations.md)
- [Database schema](../database/schema.md) — the PostgreSQL version floor the `postgres` image must satisfy
- [Provider pattern](../architecture/provider-pattern.md)
