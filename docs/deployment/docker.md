---
title: LearnFlow Docker Strategy
status: approved
owner: development-and-operations
last_updated: 2026-07-30
related:
  - ../00-project-context.md
  - environments.md
  - ../development/tech-stack.md
  - ../development/folder-structure.md
---

# LearnFlow Docker Strategy

## Purpose

Define a reproducible local LearnFlow environment so the application, PostgreSQL, and ChromaDB can run consistently on another developer’s machine without separate native database setup.

## Initial Compose Topology

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

Compose supplies these variables to the backend and frontend services. When a container serves the
backend through `python -m app.main`, `API_HOST` must be `0.0.0.0` rather than the local default of
`127.0.0.1`, or the service will not accept connections from outside the container. A container that
invokes uvicorn directly must pass `--host 0.0.0.0` instead, because that form does not read
`API_HOST`.

## Local Development Commands

The final README will provide tested commands. The expected workflow is:

```bash
# Build/start local services
docker compose up --build

# Start in the background
docker compose up --build -d

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

- Backend image builds from `docker/backend.Dockerfile`.
- Frontend image builds from `docker/frontend.Dockerfile`.
- Use `.dockerignore` to exclude virtual environments, node modules, Git metadata where unnecessary, learner data, secrets, and build artifacts.
- Keep image build stages reproducible; do not rely on untracked local files.

## Database and Seed Workflow

On a new local environment:

1. Start Compose services.
2. Apply Alembic migrations from the backend workflow.
3. Run the approved idempotent GATE CSE curriculum seed/import process.
4. Confirm backend health and curriculum-read endpoints.

The application must not silently create schema changes at startup outside the Alembic migration workflow.

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
- [Technology stack](../development/tech-stack.md)
- [Database migrations](../database/migrations.md)
- [Provider pattern](../architecture/provider-pattern.md)
