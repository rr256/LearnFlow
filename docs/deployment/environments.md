---
title: LearnFlow Environments and Configuration
status: approved
owner: development-and-operations
last_updated: 2026-07-29
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

## Configuration Groups

### Application

```text
APP_ENV
APP_LOG_LEVEL
API_HOST
API_PORT
FRONTEND_ORIGIN
```

### Database

```text
DATABASE_URL
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
```

### RAG and Storage

```text
RESOURCE_STORAGE_PROVIDER
RESOURCE_STORAGE_PATH
CHROMA_URL
EMBEDDING_PROVIDER
EMBEDDING_MODEL
```

### AI Provider

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

- Include every configuration variable required for a fresh local setup.
- Use safe non-secret placeholders.
- Explain values that have non-obvious format/meaning.
- Not contain developer-specific local paths.
- Be updated in the same change as a new required configuration variable.

Example form:

```text
APP_ENV=local
DATABASE_URL=postgresql://learnflow:CHANGE_ME@postgres:5432/learnflow
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

## Local Environment

The local environment uses:

- Docker Compose services for frontend, backend, PostgreSQL, and ChromaDB.
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
- [Docker strategy](docker.md)
- [CI/CD](ci-cd.md)
- [Technology stack](../development/tech-stack.md)
- [Non-functional requirements](../requirements/non-functional.md)
- [Provider pattern](../architecture/provider-pattern.md)
