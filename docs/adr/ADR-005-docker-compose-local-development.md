---
title: "ADR-005: Use Docker Compose for Local Development"
status: accepted
owner: development-and-operations
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - ../deployment/docker.md
  - ../deployment/environments.md
  - ../development/tech-stack.md
---

# ADR-005: Use Docker Compose for Local Development

## Status

Accepted — 2026-07-29

## Context

LearnFlow contains a web frontend, FastAPI backend, PostgreSQL database, ChromaDB vector store, local file storage, and host-based Ollama. The project should be easy to run on another local machine without requiring every contributor to install and configure database/vector services manually.

The MVP is local-first, so a full cloud deployment platform or Kubernetes cluster would add complexity without helping the immediate learner workflow.

## Decision

Use Docker Compose as the standard local environment coordinator.

The initial Compose topology includes:

```text
frontend
backend
postgres
chromadb
```

Ollama remains on the host machine initially and is accessed by the backend through a configured endpoint.

Persistent PostgreSQL, ChromaDB, and learner-resource data use configured local volumes/mounts outside Git.

## Consequences

### Positive

- Contributors get a consistent local service topology.
- PostgreSQL and ChromaDB do not need native host installation.
- Environment setup, ports, volumes, and health checks become documented/repeatable.
- The project is prepared for future container-based deployment without committing to cloud infrastructure now.
- Docker isolates runtime dependencies from the developer’s global environment.

### Negative

- Docker Desktop adds resource usage and a learning/setup step.
- Volume management requires care to avoid accidental learner-data deletion.
- Host-to-container Ollama networking must be configured per supported local environment.
- Docker Compose does not itself provide production-grade scaling, secrets, monitoring, or backup operations.

### Mitigations

- Document safe start/stop commands and explicitly warn that volume deletion is destructive.
- Use environment configuration for endpoints, ports, paths, and models.
- Add health/readiness checks for essential services.
- Keep local data out of Git and document backup/restore during hardening.
- Treat hosted deployment as a separate future decision.

## Alternatives Considered

### Native Local Installation for Every Service

Ask each contributor to install PostgreSQL, ChromaDB, and supporting tools directly on their machine.

**Rejected:** inconsistent versions/configuration and harder onboarding for collaborators.

### Containerize Ollama Immediately

Run Ollama and downloaded models in Docker Compose from the beginning.

**Rejected:** the learner already has Ollama installed, models can be large, and host installation simplifies the initial local workflow. Containerized Ollama remains a future option.

### Kubernetes From the Start

Use Kubernetes for local development and future production parity.

**Rejected:** excessive operational complexity for a local personal MVP.

## Implementation Notes

- Use `compose.yaml` at repository root and Dockerfiles under `docker/`.
- Configure service endpoints through `.env`/environment variables.
- Do not mount broad host directories, user home directories, or source-control secrets into containers.
- Use named volumes or controlled storage mounts for PostgreSQL, ChromaDB, and learner resources.
- Do not run `docker compose down -v` as a routine stop command because it can delete persistent local data.
- Database migrations remain an explicit Alembic workflow; application startup must not silently mutate schema.

## Related Documents

- [Project context](../00-project-context.md)
- [Docker strategy](../deployment/docker.md)
- [Environments](../deployment/environments.md)
- [Technology stack](../development/tech-stack.md)
- [Database migrations](../database/migrations.md)
- [Architecture decision register](../architecture/decisions.md)
