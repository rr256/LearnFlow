---
title: LearnFlow Environments and Configuration
status: approved
owner: development-and-operations
last_updated: 2026-08-20
related:
  - ../00-project-context.md
  - docker.md
  - ci-cd.md
  - ../development/tech-stack.md
  - ../database/migrations.md
  - ../adr/ADR-011-sqlalchemy-persistence-implementation.md
  - ../adr/ADR-013-examination-schedule-and-study-goal.md
  - ../adr/ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ../adr/ADR-039-source-grounded-study-answers.md
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
| `APP_DEFAULT_TIMEZONE` | `Asia/Kolkata` | An IANA timezone name, validated at startup against the standard library's zone database |

`APP_DEFAULT_TIMEZONE` is the timezone a learner record is created with. It is core runtime under
ADR-009: it describes how this installation runs, selects no capability adapter, and names no vendor.
The default suits GATE CSE, the learning program LearnFlow ships with; a learner elsewhere sets it
once rather than editing code. It is validated through `zoneinfo`, so a typo fails at startup naming
the field rather than surfacing later as a study plan whose days land a day out. No dependency was
added for it — `tzdata` already ships as a dependency of psycopg. See
[ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md), which settles it as one of the open
items [ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md) recorded.

`API_CORS_ALLOWED_ORIGINS` remains a planned core-runtime setting for when CORS middleware is
introduced. It carries the `API_` prefix because a CORS allow-list governs how the API process serves
requests; it selects no capability adapter and names no vendor. **The frontend did not fire that
trigger.** Its learner-facing pages render as React Server Components, so the Next.js server calls
the API and the browser never does; there is no cross-origin request to allow. A future
browser-side call is what introduces both the middleware and this variable.

`APP_LOG_LEVEL` is matched case-insensitively — `debug`, `Debug`, and `DEBUG` are all accepted — and
normalised internally to the uppercase canonical form. Write it uppercase in `.env` files and
documentation examples so the stored and configured values read the same.

`API_HOST` and `API_PORT` are consumed by the `python -m app.main` entry point, which serves the
application on that address. The `python -m uvicorn app.main:app` form takes its host and port from
uvicorn's own arguments instead; use it for reload workflows and ASGI tooling.

`API_BASE_URL` is **not** a backend variable. `API_HOST`/`API_PORT` are the address the backend
binds to; the client-facing base URL is frontend configuration, catalogued below.

### Frontend

**Implemented.** Read by `frontend/lib/config.ts` today.

| Variable | Default | Accepted values |
| --- | --- | --- |
| `API_BASE_URL` | `http://127.0.0.1:8000` | An absolute `http` or `https` URL naming the LearnFlow API. A trailing slash is trimmed. |

It is core runtime under [ADR-009](../adr/ADR-009-configuration-naming-and-validation.md): it
describes how the frontend process runs, selects no capability adapter, and names no vendor. ADR-009
fixed the name when it separated the address a client calls from the address the backend binds to.

**It is read on the server only, and deliberately carries no `NEXT_PUBLIC_` prefix**, which is what
would place a value in a browser bundle. Learner-facing pages render as React Server Components, so
the API address never leaves the server — satisfying the rule above that frontend-visible values
expose no infrastructure endpoints.

The default is safe because it names no external system a browser can reach and carries no
credential: it is the backend as published on the host loopback interface, which is what a host-side
`npm run dev` needs. Compose overrides it with a fixed value naming the `backend` service, for the
same reason `DATABASE_URL` is fixed there; see [Docker strategy](docker.md#the-frontend-service). The
value is validated when it is read, so a malformed URL fails with a message naming the variable
rather than surfacing later as a failed request.

Next.js reads `.env` files from the frontend project directory rather than the repository root, so a
host-side run takes this value from `frontend/.env.local` or the shell. `.gitignore` excludes both.

### Database

**Implemented.** `DATABASE_URL` is read by `backend/app/composition/config.py`; the `POSTGRES_*`
values create and are used to reach the Compose `postgres` service.

| Variable | Default | Accepted values |
| --- | --- | --- |
| `DATABASE_URL` | *none — required* | A PostgreSQL URL including the driver, such as `postgresql+psycopg://user:password@host:5432/database`. Validated as a PostgreSQL DSN; another database's scheme is rejected. |
| `POSTGRES_DB` | `learnflow` | Database name created by the `postgres` service. |
| `POSTGRES_USER` | `learnflow` | Role created by the `postgres` service. |
| `POSTGRES_PASSWORD` | `learnflow` | Local development password. Not a secret to protect, and never reused outside local development. |

`DATABASE_URL` is the one variable with no default. Every other setting describes how the process
itself runs and has a safe universal value; a database URL names an external system and carries
credentials, so any default would be a guess pointing somewhere real. A missing value fails at
startup naming the field. Note the consequence: `python -m app.main` needs configuration to start,
where previously the documented defaults sufficed.

`DATABASE_URL` is a capability-level setting under ADR-009 — it survives a change of relational
database — while `POSTGRES_*` are vendor settings that do not. Compose builds the backend's
`DATABASE_URL` from the `POSTGRES_*` values so the two cannot drift; see
[Docker strategy](docker.md).

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

**Implemented, except the embedding model.** `AI_PROVIDER`, `AI_REQUEST_TIMEOUT_SECONDS`,
`OLLAMA_BASE_URL`, and `OLLAMA_CHAT_MODEL` are read at startup and are in `.env.example`.
`OLLAMA_EMBEDDING_MODEL` stays **planned**: nothing embeds anything, and it joins the file with the
adapter that reads it.

```text
AI_PROVIDER                  ollama          (the only implemented adapter)
AI_REQUEST_TIMEOUT_SECONDS   60              (capability-level; > 0 and <= 600)
OLLAMA_BASE_URL              http://127.0.0.1:11434
OLLAMA_CHAT_MODEL            llama3.1:8b
OLLAMA_EMBEDDING_MODEL                       (planned)
```

`AI_PROVIDER` is validated against the adapters that exist, so an unknown value fails at startup with
a named field rather than at the first question a learner asks. `OLLAMA_BASE_URL` accepts `http` and
`https` only — a security boundary rather than tidiness, since it is what stops a `file://` value
from turning an outbound request into a local file read.

`AI_REQUEST_TIMEOUT_SECONDS` is capability-level under ADR-009: it bounds any AI provider and
survives a change of one. There is deliberately **no retry setting**, because there is no retry.

**Compose passes all four to the `backend` service, and to no other.** `AI_PROVIDER`,
`AI_REQUEST_TIMEOUT_SECONDS`, and `OLLAMA_CHAT_MODEL` interpolate from the shell or `.env` as usual.
`OLLAMA_BASE_URL` does **not**: it is fixed to `http://host.docker.internal:11434`, because the value
above names `127.0.0.1`, which inside a container is the container itself rather than the host
running Ollama. That is the same reasoning `DATABASE_URL` and the frontend's `API_BASE_URL` already
follow.

`host.docker.internal` is provided natively by Docker Desktop on macOS and Windows. Docker Engine on
Linux does not provide it, so `compose.yaml` maps it through `extra_hosts` to the special
`host-gateway` value and the one address works on all three.

**`OLLAMA_CONTAINER_BASE_URL` overrides the containerised address** — for an Ollama on another port
or another machine. It is a **Compose-only variable**: nothing in the backend reads it, so it is
absent from the catalogue groups above and from `.env.example`.

**No AI setting reaches the `frontend` service.** Its environment feeds a server that renders pages
for a browser, and nothing about the provider belongs there — not the address, not the model, and not
the fact that one is configured. A test asserts it; see
[the Docker topology test](../development/coding-standards.md#local-quality-checks).

See [Docker strategy](docker.md).

**No credential is defined here and none is read.** The selected provider runs locally and
authenticates nothing, so LearnFlow has no API key in configuration, in `.env.example`, or in the
environment it expects. See [ADR-004](../adr/ADR-004-ollama-local-ai-provider.md) and
[ADR-039](../adr/ADR-039-source-grounded-study-answers.md).

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

The committed file therefore currently contains exactly the fourteen implemented variables:

```text
APP_ENV=local
APP_LOG_LEVEL=INFO
APP_DEFAULT_TIMEZONE=Asia/Kolkata
API_HOST=127.0.0.1
API_PORT=8000
API_BASE_URL=http://127.0.0.1:8000
DATABASE_URL=postgresql+psycopg://learnflow:learnflow@127.0.0.1:5432/learnflow
POSTGRES_DB=learnflow
POSTGRES_USER=learnflow
POSTGRES_PASSWORD=learnflow
AI_PROVIDER=ollama
AI_REQUEST_TIMEOUT_SECONDS=60
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_CHAT_MODEL=llama3.1:8b
```

That block is a transcript of the committed file, so the two change together or not at all.

It also carries `TEST_DATABASE_URL` as a commented-out example. That variable is read by the test
suite rather than by the application, and leaving it set would point the integration tests at a real
database, so it is documented but not active by default.

Planned entries such as `CHROMA_URL` and `OLLAMA_EMBEDDING_MODEL` are catalogued in the groups above
and join `.env.example` in the change that implements their consumer.

## Local Environment

The local environment target uses:

- Docker Compose services for frontend, backend, PostgreSQL, and ChromaDB. `compose.yaml` currently
  defines the `frontend`, `backend`, and `postgres` services; see [Docker strategy](docker.md).
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

#### `TEST_DATABASE_URL`

**Implemented.** A test-harness variable, not application configuration: `backend/tests/integration/`
reads it directly and `config.py` never sees it. It is catalogued here rather than with the
application variables above for that reason.

| Variable | Default | Accepted values |
| --- | --- | --- |
| `TEST_DATABASE_URL` | *none — tests skip when unset* | A PostgreSQL URL naming a **disposable** database. The migration tests create and drop its tables. |

It deliberately does not fall back to `DATABASE_URL`. A fallback would run destructive schema tests
against the development database the first time someone forgot to set it, which is exactly what the
first rule above forbids. Unset means skip, and CI fails rather than skips by verifying the database
is reachable before running the tests.

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
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](../adr/ADR-011-sqlalchemy-persistence-implementation.md) — why `DATABASE_URL` has no default
- [ADR-013: Model an examination period as a published window of reference data](../adr/ADR-013-examination-schedule-and-study-goal.md) — why `APP_DEFAULT_TIMEZONE` exists and what sets its default
- [Docker strategy](docker.md)
- [ADR-015: Build the frontend on Next.js and reach the API from the server](../adr/ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the decision that made `API_BASE_URL` server-side frontend configuration
- [CI/CD](ci-cd.md)
- [Database migrations](../database/migrations.md) — the workflow `DATABASE_URL` and `TEST_DATABASE_URL` serve
- [Technology stack](../development/tech-stack.md)
- [Non-functional requirements](../requirements/non-functional.md)
- [Provider pattern](../architecture/provider-pattern.md)
