---
title: LearnFlow Environments and Configuration
status: approved
owner: development-and-operations
last_updated: 2026-07-30
related:
  - ../00-project-context.md
  - docker.md
  - ci-cd.md
  - ../development/tech-stack.md
---

# LearnFlow Environments and Configuration

## Purpose

Define how LearnFlow separates environment-specific configuration from source code and safely evolves from local development to future test/staging/production environments.

## Current Environment Strategy

The MVP is local-first. Local development is the only required runtime environment initially.

Future environments are documented now to prevent local assumptions from becoming architecture constraints.

| Environment | Status | Purpose |
| --- | --- | --- |
| `local` | Required now | Daily development and personal use through Docker Compose + host Ollama. |
| `test` | Required when automated tests begin | Isolated, reproducible test configuration and data. |
| `staging` | Future | Pre-production validation before any hosted/public release. |
| `production` | Future | Hosted/shared runtime for real users. |

## Configuration Principles

- Configuration is supplied through environment variables or environment-specific deployment configuration.
- Source code contains no real secrets, personal paths, provider credentials, or machine-specific endpoint assumptions.
- `.env.example` documents required variable names and safe placeholder examples.
- `.env` files with real local values are ignored by Git.
- The backend validates required configuration at startup and reports safe actionable errors.
- Provider selection occurs in the composition root, not in domain/application logic.
- Frontend-visible environment values must never include database URLs, storage credentials, or private provider secrets.

## Variable Naming

Every configuration variable belongs to one of three categories, defined in
[ADR-009](../adr/ADR-009-configuration-naming-and-validation.md):

| Category | Form | Purpose |
| --- | --- | --- |
| Core runtime | `APP_*`, `API_*` | How the application process itself runs. |
| Capability | `<CAPABILITY>_PROVIDER`, plus capability-level settings | Which adapter fulfils an application port, and settings that stay meaningful whichever adapter is chosen. |
| Vendor | `<VENDOR>_<SETTING>` | Settings meaningful only to one specific vendor. |

For example, `AI_PROVIDER=ollama` selects the adapter (capability) and `OLLAMA_CHAT_MODEL`
configures it (vendor). Switching providers keeps the first and replaces the second.

## Configuration Groups

This document is the authoritative catalogue of LearnFlow configuration variables. Other documents
link here rather than restating the list.

A variable appears in `.env.example` only once the code that reads it exists. Variables listed below
but not yet in `.env.example` are planned, not active.

### Application

**Implemented.** These are read by `backend/app/composition/config.py` today.

| Variable | Default | Accepted values |
| --- | --- | --- |
| `APP_ENV` | `local` | `local`, `test`, `staging`, `production` |
| `APP_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` — accepted in any casing |
| `API_HOST` | `127.0.0.1` | Bind address; use `0.0.0.0` inside a container |
| `API_PORT` | `8000` | Integer, 1–65535 |

`API_CORS_ALLOWED_ORIGINS` is a planned core-runtime setting for when CORS middleware is introduced.
It carries the `API_` prefix because a CORS allow-list governs how the API process serves requests;
it selects no capability adapter and names no vendor.

`APP_LOG_LEVEL` is matched case-insensitively — `debug`, `Debug`, and `DEBUG` are all accepted — and
normalised internally to the uppercase canonical form. Write it uppercase in `.env` files and
documentation examples so the stored and configured values read the same.

`API_HOST` and `API_PORT` are consumed by the `python -m app.main` entry point, which serves the
application on that address. The `python -m uvicorn app.main:app` form takes its host and port from
uvicorn's own arguments instead; use it for reload workflows and ASGI tooling.

`API_BASE_URL` is **not** a backend variable. `API_HOST`/`API_PORT` are the address the backend
binds to; the client-facing base URL is future frontend configuration.

### Database

**Planned.** Added when persistence is implemented.

```text
DATABASE_URL
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
```

### RAG and Storage

**Planned.** Added when the storage and retrieval adapters are implemented.

```text
RESOURCE_STORAGE_PROVIDER
RESOURCE_STORAGE_PATH
CHROMA_URL
EMBEDDING_PROVIDER
```

The embedding model is configured by the vendor-specific `OLLAMA_EMBEDDING_MODEL` below. There is
no generic `EMBEDDING_MODEL` variable; ADR-009 removed it because two variables for one setting left
the precedence undefined.

### AI Provider

**Planned.** Added when the AI and embedding adapters are implemented.

```text
AI_PROVIDER
OLLAMA_BASE_URL
OLLAMA_CHAT_MODEL
OLLAMA_EMBEDDING_MODEL
```

### Future Cloud Providers

```text
OPENAI_API_KEY
AZURE_STORAGE_CONNECTION_STRING
AZURE_OPENAI_ENDPOINT
```

Future provider variables remain absent from the MVP `.env` unless that provider is explicitly enabled. Never add placeholder real credentials or encourage configuration for unused cloud services.

## `.env.example` Rules

The committed `.env.example` must:

- Include every **implemented** configuration variable, so a fresh local setup needs nothing else.
- **Exclude planned variables until the code that reads them exists.** A variable in `.env.example`
  that nothing consumes asks contributors to configure a service that is not there, and cannot be
  validated at startup.
- Use safe non-secret placeholders.
- Explain values that have non-obvious format/meaning.
- Not contain developer-specific local paths.
- Be updated in the same change that introduces or removes a configuration variable.

The committed file therefore currently contains exactly the four implemented variables:

```text
APP_ENV=local
APP_LOG_LEVEL=INFO
API_HOST=127.0.0.1
API_PORT=8000
```

Planned entries such as `DATABASE_URL`, `AI_PROVIDER`, and `OLLAMA_BASE_URL` are catalogued in the
groups above and join `.env.example` in the change that implements their consumer.

## Local Environment

The local environment target uses:

- Docker Compose services for frontend, backend, PostgreSQL, and ChromaDB. `compose.yaml` currently
  defines the `backend` service only; see [Docker strategy](docker.md).
- Host-machine Ollama for local generation/embedding models.
- Local storage provider for learner-owned source resources.
- Private local volumes for PostgreSQL, ChromaDB, and resource storage.

Local configuration may use Docker service names internally, such as `postgres` and `chromadb`. Application code must not hardcode those names; configuration provides endpoints.

## Test Environment

The test environment must be isolated from personal learner data.

- Never run automated tests against the normal local PostgreSQL volume or learner resource storage.
- Use a dedicated test database/volume or ephemeral containerized database.
- Use temporary storage locations for file/resource tests.
- Use fake/mocked AI/retrieval providers for deterministic domain/application tests.
- Run live-provider integration tests only when explicitly configured and safe.

## Future Staging and Production Boundaries

Before staging/production exists, the following rules still apply:

- Use distinct databases, storage locations, secrets, and provider configurations per environment.
- Never promote local learner data into staging/production by default.
- Run database migrations as a controlled deployment action.
- Use managed secret storage or equivalent secure environment injection for hosted secrets.
- Treat cloud provider usage as an explicit privacy/cost decision documented through architecture and ADRs.
- Do not expose internal provider/database services directly to public clients.

## Configuration Validation

Configuration is validated in `backend/app/composition/config.py` when `Settings` is constructed.
Invalid values raise before `create_app()` returns an application, so the process fails fast rather
than starting in an unusable state. See [ADR-009](../adr/ADR-009-configuration-naming-and-validation.md).

The backend should validate at startup:

- Required values are present for the selected environment.
- The configured provider names are supported.
- URLs/paths use valid format.
- Required model names are configured when Ollama/embedding features are enabled.
- Incompatible configuration combinations fail early with safe messages.

Example: if `AI_PROVIDER=ollama`, the backend requires an Ollama endpoint and configured chat model; it must not try to use cloud credentials.

## Secrets Policy

- Never commit secrets to Git, docs, screenshots, prompts, logs, or issue reports.
- Rotate a secret immediately if it is accidentally exposed.
- Do not print full connection strings or API keys in normal logs.
- Use least-privilege credentials when hosted infrastructure is introduced.
- Keep private learner files and test screenshots out of configuration repositories and CI artifacts.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-005: Use Docker Compose for local development](../adr/ADR-005-docker-compose-local-development.md) — the decision this configuration serves
- [ADR-009: Name and validate configuration variables explicitly](../adr/ADR-009-configuration-naming-and-validation.md) — the naming categories and validation approach this catalogue follows
- [Docker strategy](docker.md)
- [CI/CD](ci-cd.md)
- [Technology stack](../development/tech-stack.md)
- [Non-functional requirements](../requirements/non-functional.md)
- [Provider pattern](../architecture/provider-pattern.md)
