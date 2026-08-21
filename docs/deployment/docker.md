---
title: LearnFlow Docker Strategy
status: approved
owner: development-and-operations
last_updated: 2026-08-20
related:
  - ../00-project-context.md
  - environments.md
  - ci-cd.md
  - ../requirements/non-functional.md
  - ../adr/ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ../adr/ADR-016-learner-onboarding-api-contracts.md
  - ../development/tech-stack.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../database/migrations.md
  - ../database/schema.md
  - ../api/endpoints.md
  - ../adr/ADR-040-learner-uploaded-resource-files.md
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

`compose.yaml` currently defines the `frontend`, `backend`, and `postgres` services.

| Service | State |
| --- | --- |
| `frontend` | Implemented — builds from `docker/frontend.Dockerfile`; build verified in CI. |
| `backend` | Implemented — builds from `docker/backend.Dockerfile`; build verified in CI. |
| `postgres` | Implemented — `postgres:18-alpine` with a named volume and a `pg_isready` health check. |
| `chromadb` | Not implemented — no code reads `CHROMA_URL`. |

Each remaining service joins `compose.yaml` in the change that implements the code consuming it. This
follows the rule in [ADR-009](../adr/ADR-009-configuration-naming-and-validation.md) that a
configuration variable is added when its consumer exists. `postgres` joined when the backend gained a
configured engine and an Alembic environment that read `DATABASE_URL`; `frontend` joined when a
Next.js application existed that reads `API_BASE_URL` and calls the curriculum endpoints; `chromadb`
is still waiting on its consumer.

### The `postgres` service

| Decision | Value |
| --- | --- |
| Image | `postgres:18-alpine`, pinned to a major version so a rebuild cannot silently move the local database to a new major. The version floor is owned by [database schema](../database/schema.md), which requires PostgreSQL 15 or later. |
| Persistent data | The named volume `postgres_data`, mounted at `/var/lib/postgresql` — **not** `/var/lib/postgresql/data`. See the note below. |
| Health check | `pg_isready` against the configured user and database. |
| Published port | `127.0.0.1:5432` only, so the database is unreachable from other devices. It is published at all so a contributor can run Alembic and the integration tests from the host. |
| Credentials | `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`, each defaulting to `learnflow`. Local development values, not secrets. |

**The volume is mounted at `/var/lib/postgresql`, one level above the path most PostgreSQL Compose
examples use.** From version 18 the official images store data in a major-version-specific
subdirectory under that single mount — `/var/lib/postgresql/18/docker` — so that a later
`pg_upgrade --link` can move between majors without crossing a mount-point boundary. An image of 18
or later **refuses to start** when it finds a volume at the older `/var/lib/postgresql/data` path,
reporting it as an "unused mount/volume" rather than risking a botched upgrade. Upstream discussion:
[docker-library/postgres#1259](https://github.com/docker-library/postgres/pull/1259).

This was found the first time the stack was ever started, on 2026-08-08: `compose.yaml` pinned
`postgres:18-alpine` while mounting the pre-18 path, and `postgres` exited `1` on startup, taking
`backend` and `frontend` with it through their `depends_on` conditions. **No CI check could have
caught it** — the `containers` job validates the topology and builds the images but starts no
container, which is precisely the limit [verification status](#verification-status) records. The
volume was empty, so nothing was lost.

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

### The `frontend` service

| Decision | Value |
| --- | --- |
| Base image | `node:24-alpine`, matching the Node version the frontend requires and CI uses. |
| Build | Multi-stage — dependencies from the committed lockfile, then `next build`, then a runtime stage. |
| Copied artefact | The `standalone` output only. `output: "standalone"` in `next.config.ts` emits a self-contained server with just the traced dependencies, so the runtime stage carries no `node_modules` tree. |
| Process user | The unprivileged `node` user the base image ships, not root. |
| Entry point | `node server.js`, the standalone server. |
| Published port | `127.0.0.1:3000` only, so the application is not reachable from other devices. |
| Health check | `GET /health` probed with Node's global `fetch`, so the image needs no extra package. That route is static and reaches nothing — see below. |
| Telemetry | Disabled through `NEXT_TELEMETRY_DISABLED=1` in the image and in CI. LearnFlow is local-first under [NFR-001](../requirements/non-functional.md#nfr-001-local-first-privacy); no build reports anything outward. |

**The browser never calls the API.** Learner-facing pages render as React Server Components, and the
setup screen's writes go through a server action, so the Next.js server makes every API call — reads
and writes alike — and sends HTML. Three consequences:

- The API needs no CORS allow-list, and `API_CORS_ALLOWED_ORIGINS` stays a planned setting rather
  than one this change implements. The first write path did not alter this, per
  [ADR-016](../adr/ADR-016-learner-onboarding-api-contracts.md).
- `API_BASE_URL` is server-side configuration. It carries no `NEXT_PUBLIC_` prefix, so it never
  enters a client bundle — which is what the rule against browser-visible infrastructure values in
  [environments](environments.md#configuration-principles) requires.
- The image builds without a running backend. Every home, curriculum, and setup route is
  `force-dynamic`, so nothing is fetched while prerendering.

**The frontend's health check probes its own `/health`, not `/`.** That route is `force-static` and
reaches nothing — no API, no database, no other service — so the probe answers exactly one question:
is this frontend process responding?

Probing `/` answered that question too, but only by rendering the home screen, which calls the API up
to three times to build a page no probe reads. Every ten seconds, for the life of the container.
That is the reason for the change: a liveness check should not generate backend traffic.

**It was not a correctness fix.** Probing `/` did not report the container unhealthy when the backend
was down: the home screen catches an unreachable API and renders its notice with a `200`, so the old
probe passed. The frontend renders per request and needs no API at startup, and both probes reflect
that — the new one just does so without asking the backend anything.

This is a different endpoint from the backend's `GET /health`, on a different service. The backend's
is the operational endpoint described in
[API conventions](../api/conventions.md#operational-endpoints-are-unversioned); the frontend's reports
only that the Next.js server process is serving. Both answer a flat `{"status": "ok"}`, so probe
tooling reads the same field from either.

`compose.yaml` fixes `API_BASE_URL` to `http://backend:${API_PORT:-8000}` rather than interpolating
it whole, for the reason `DATABASE_URL` is fixed: a developer's `.env` names the backend's published
loopback port, and inside the frontend container that address is the container itself. The port still
follows `API_PORT`, so the two services cannot drift apart.

The `frontend` service waits for `backend` to report healthy. As with `backend` and `postgres`, that
is convenience rather than necessity — the frontend renders per request and needs no API at startup —
but waiting means the first page a learner opens meets a backend ready to answer.

### Verification status

**Both image builds and the topology are verified in CI.** The `containers` job first ran on pull
request #7 and passed: `docker compose config -q` validated the topology and
`docker build -f docker/backend.Dockerfile .` built the backend image. The frontend image build
joined the same job with the frontend application, and first passed on pull request #13 — run
`30850601752`, on commit `588cbfc`, where `Validate Compose topology`, `Build backend image`, and
`Build frontend image` all succeeded. It failed on that pull request's two earlier runs, for a
lockfile `npm ci` could not install. The job runs again on every pull request and every push to
`main`, so a change that breaks either build is caught there.

The `frontend` **service definition** was validated earlier and more often than the image that serves
it: `docker compose config -q` reads every service in the file, so it covered `frontend` from that
service's first run on pull request #13, and passed on all three of that pull request's runs —
including the two whose frontend image build failed. Be precise about what that check is worth. It
proves the file parses, interpolates its variables, and matches the Compose schema. It does not
prove the service's ports, environment, health check, or `depends_on` are *correct*, only that they
are well-formed.

Two further limits, both still true after run `30850601752`:

- **CI still starts no container.** It validates and builds; it does not run `docker compose up`, so
  no health-check probe executes there and no request is served through a container in CI. A
  successful `docker build` shows that an image can be produced, not that the process inside it runs,
  serves, or reaches another service. That gap is what the local run below closed, and it is still
  open in CI.
- **Container commands remain outside the canonical
  [local quality checks](../development/coding-standards.md#local-quality-checks)**, which cover the
  checks needing nothing beyond Python and Node.js. Running them locally is optional and needs a
  Docker installation.

#### First local run — 2026-08-08

**The stack has now been started, once, on a Windows 11 workstation with Docker Desktop 29.6.2 and
Compose v5.3.1.** This supersedes the previous statements that no container had been started and that
the commands had never been run locally.

It found one defect immediately, which is recorded above under
[the `postgres` service](#the-postgres-service): the volume was mounted at the pre-18
`/var/lib/postgresql/data` while the image was pinned to `postgres:18-alpine`, so `postgres` exited
`1` and took `backend` and `frontend` with it. With the mount corrected, the whole sequence ran.

What the run demonstrated, for the first time:

- `docker compose up -d` starts all three services, and **both health checks pass** —
  `postgres` reports healthy through `pg_isready`, `backend` through `GET /health`, and `frontend`
  through its own static `/health`.
- The `depends_on` conditions work in both directions: they held `backend` back while `postgres` was
  failing, and released it once `postgres` was healthy.
- **The backend reaches `postgres` over the Compose network** by service name, and **the frontend
  reaches `backend`** the same way — the home screen rendered the seeded study goal, which it can only
  do by calling the API.
- Host-side Alembic reaches the published port: all seven migrations applied against the container.
- Both seeds and `set_study_goal` ran against it, and `GET /api/v1/curriculum/programs` returned the
  seeded program over the published backend port.
- **No API address appeared in the served HTML**, confirming through a container what
  [ADR-015](../adr/ADR-015-frontend-foundation-and-server-rendered-api-access.md) decided.

What it did **not** demonstrate: any behaviour under restart, upgrade, or data already in the volume.
The volume was created empty by this run, so `pg_upgrade` across majors and the mount-boundary
reasoning behind the corrected path are still untested in practice.

The migrations themselves are verified separately and more strongly: the CI `database` job applies
them to a real PostgreSQL service container on every pull request. That job uses a GitHub Actions
service rather than Compose, so it exercises the schema without exercising this topology.

The Milestone 1 Compose item stays unticked, but now on **one** count rather than two: the topology
covers four services and three exist, `chromadb` still waiting on its consumer. The other count — that
no container had been started — is discharged by
[the first local run](#first-local-run-2026-08-08) above.
[Milestones](../roadmap/milestones.md) records the same.

## Service Responsibilities

| Service | Responsibility | Persistent data |
| --- | --- | --- |
| `frontend` | Learner-facing Next.js application. | None in normal runtime. |
| `backend` | FastAPI routes, application use cases, provider wiring, ingestion coordination. | Named volume `resource_files`, mounted at `/var/lib/learnflow/resources` — learner-uploaded PDF bytes (RES-014 to RES-017). |
| `postgres` | Curriculum, learners, goals, plans, progress, assessments, resource metadata. | Named PostgreSQL volume. |
| `backend` (files) | Learner-uploaded PDF bytes (RES-014 to RES-017). | Named volume `resource_files`, mounted into `backend` alone. |
| `chromadb` | Derived chunks/vectors and retrieval metadata. | Named ChromaDB volume. |
| Host `ollama` | Local generation and embedding models. | Managed by host Ollama installation. |

## Networking

- Compose services communicate over the internal Compose network using service names, such as `backend` and `postgres`.
- The frontend communicates with the backend through `API_BASE_URL`, resolved on the Next.js server. No API address is browser-visible, and no browser-visible value may expose database or provider credentials.
- **The backend reaches host Ollama through `host.docker.internal`, and `compose.yaml` configures it.** `OLLAMA_BASE_URL` is fixed on the `backend` service to `http://host.docker.internal:11434` rather than interpolated, because a developer's own value names `127.0.0.1`, which inside a container is the container itself. It is **not hardcoded in application logic**: the adapter reads whatever configuration gives it, and `OLLAMA_CONTAINER_BASE_URL` overrides the containerised address for an Ollama elsewhere.
- **`extra_hosts` maps `host.docker.internal` to `host-gateway` on the `backend` service.** Docker Desktop provides the name natively on macOS and Windows; Docker Engine on Linux does not, so the mapping makes one address work on all three. It is the only route out of the backend container, and it reaches the host that started it and nothing beyond — a learner's passages stay on their own machine exactly as in a host-side run.
- **No AI setting reaches the `frontend` service**, whose environment feeds a server rendering pages for a browser. `API_BASE_URL` is the only value it carries. `backend/tests/integration/test_docker_topology.py` asserts both halves of this wherever Docker is installed, and — where the local Compose network is up — additionally runs a backend container against a fake Ollama on the host to prove the path works, without making a real external call.
- Expose only the ports needed for local development; production exposure is a later concern.

## Persistent Data

Use named volumes or configured local mounts for durable runtime data:

```text
postgres_data    PostgreSQL database files, mounted at /var/lib/postgresql
resource_files   Learner-uploaded PDF bytes, mounted at /var/lib/learnflow/resources
chroma_data      ChromaDB/vector index files                      (planned)
```

### What survives, and what does not

`resource_files` exists today and holds a learner's uploaded PDFs
([ADR-040](../adr/ADR-040-learner-uploaded-resource-files.md)). It is mounted into the **`backend`
service alone** — the frontend never reads a file, and keeping it out of `postgres` is what lets the
database and the files be backed up and restored independently.

**It survives normal operation:**

- `docker compose down` — the volume is **not** removed.
- `docker compose up --build`, and any image rebuild.
- `docker compose up -d --force-recreate backend`, and container recreation generally.

**One command destroys it:**

- **`docker compose down -v` deletes `resource_files` and `postgres_data` together.** That is why it
  is not a routine stop command. A learner's uploaded PDFs are gone with it, and LearnFlow has no
  copy anywhere else.

### Backup is now two things

**A database backup alone does not back up uploaded files.** Since ADR-040 a learner's material lives
in two places:

- the **rows** describing each file — `resource_files` — in PostgreSQL, captured by `pg_dump`;
- the **bytes** themselves in the `resource_files` volume, which `pg_dump` does not touch at all.

Backing up one without the other leaves an inconsistent restore. Restoring a **database** older than
the volume leaves files nothing names; restoring a **volume** older than the database leaves rows
whose bytes are missing — LearnFlow reports that honestly, with a `404` on download and the row still
listed, rather than deleting the record.

A complete backup therefore copies the volume as well, for example with a throwaway container that
mounts it read-only and writes a tar to the host. Verify a restore before relying on it.

**The backend image creates the storage directory and owns it.** A named volume is initialised from
the image's directory at the mount point, ownership included; without that step a fresh volume is
root-owned and the unprivileged application user cannot write a single file into it.

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

Compose supplies these variables to the backend service, and supplies `API_BASE_URL` to the frontend
service as described under [the `frontend` service](#the-frontend-service). When a container serves the
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
docker compose logs -f frontend

# Stop services while preserving persistent data
docker compose down
```

Use `docker compose down -v` only with explicit care: it removes named volumes and deletes local PostgreSQL data **and every PDF a learner has uploaded** (`postgres_data` and `resource_files`). It must never be presented as a routine stop command.

## Startup and Health Checks

- PostgreSQL and ChromaDB should define health checks before the backend treats them as ready.
- The backend should expose a safe health/readiness endpoint.
- Backend readiness must validate required configuration and connectivity to essential local services.
- Ollama/model availability should be reported separately and clearly; the rest of the app can remain available if AI generation is unavailable.
- The frontend should display understandable dependency-unavailable states rather than generic failures.

## Resource Storage in Local Development

- Store learner resources only in a configured application storage location, not arbitrary host paths.
- Use an opaque storage key in PostgreSQL; do not return raw mounted-container or host paths to the frontend.
- A host bind mount was **considered and rejected** for learner files ([ADR-040](../adr/ADR-040-learner-uploaded-resource-files.md)): it risks committing a learner's PDFs and drags in NTFS permission and path-length problems. If one is nevertheless used during development, document the configured root and ensure it stays outside committed source folders.
- The storage-provider interface keeps a later Azure Blob Storage adapter possible.

## Images and Builds

- Backend image builds from `docker/backend.Dockerfile`. Implemented.
- Frontend image builds from `docker/frontend.Dockerfile`. Implemented.
- Use `.dockerignore` to exclude virtual environments, node modules, Git metadata where unnecessary, learner data, secrets, and build artifacts.
- Keep image build stages reproducible; do not rely on untracked local files.
- The build context is the repository root, so a Dockerfile can copy from `backend/`.
- CI validates the Compose topology and builds the backend and frontend images on every pull request;
  see [CI/CD strategy](ci-cd.md). No image is pushed to a registry.

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
7. Open <http://127.0.0.1:3000/> to see the learner's saved setup, and
   <http://127.0.0.1:3000/curriculum> to browse the same data in the frontend.

Be precise about what has been demonstrated. Steps 2 to 6 are exercised on every pull request by the
CI `database` job, which applies the migrations, runs each seed twice, sets the study goal, and reads
the curriculum endpoints over HTTP — but against an ephemeral PostgreSQL service, not through
Compose. **Steps 1 and 7 have never been run**: no container has been started, here or in CI, so
`docker compose up` and the frontend reaching the backend over the Compose network are both
unverified. See [verification status](#verification-status). The application must not silently create schema changes at startup outside
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
- [ADR-015: Build the frontend on Next.js and reach the API from the server](../adr/ADR-015-frontend-foundation-and-server-rendered-api-access.md) — why the `frontend` service renders on the server and needs no CORS
- [Non-functional requirements](../requirements/non-functional.md) — NFR-001, the local-first rule the disabled build telemetry follows
- [CI/CD strategy](ci-cd.md) — the container checks that run on every pull request
- [Repository and folder structure](../development/folder-structure.md) — where `compose.yaml`, `docker/`, and `.dockerignore` live
- [Milestones](../roadmap/milestones.md) — why the Milestone 1 Compose item is still open
- [Technology stack](../development/tech-stack.md)
- [API endpoints](../api/endpoints.md) — the endpoints step 6 of the local workflow confirms
- [Database migrations](../database/migrations.md)
- [Database schema](../database/schema.md) — the PostgreSQL version floor the `postgres` image must satisfy
- [Provider pattern](../architecture/provider-pattern.md)
