---
title: LearnFlow CI/CD Strategy
status: approved
owner: development-and-operations
last_updated: 2026-08-03
related:
  - ../00-project-context.md
  - environments.md
  - ../development/git-workflow.md
  - ../development/coding-standards.md
  - ../development/documentation-standards.md
  - docker.md
  - ../adr/ADR-010-feature-delivery-workflow.md
  - ../adr/ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ../database/migrations.md
  - ../api/endpoints.md
---

# LearnFlow CI/CD Strategy

## Purpose

Define how LearnFlow automates verification and what remains deferred.

The MVP does not require public deployment. Continuous integration protects code and documentation quality; continuous deployment remains deferred until a hosted environment is approved.

## Current Decision

### Continuous Integration

CI configuration is implemented and covers the backend, the frontend, the documentation set, the
database migrations, and the container builds. All five jobs run on every pull request targeting
`main` and on every push to `main`; the workflow applies no path filters, so a documentation-only
change runs the backend, frontend, database, and container jobs too. See
[Implemented Workflow](#implemented-workflow) below.

One limit applies to the current state:

- **Branch protection is not configured.** CI results inform review, but nothing technically prevents
  a merge while a check is failing. Branch protection is a repository setting rather than a
  repository file, and is recorded as a deferred decision in the
  [decision register](../architecture/decisions.md).

### Continuous Deployment

Do not deploy publicly during the local-first MVP. Future deployment requires separate staging/production decisions, secrets, backup/recovery plans, and an ADR where appropriate.

## CI Responsibilities

CI verifies only stable, repeatable checks:

| Area | Expected check | State |
| --- | --- | --- |
| Documentation | Front-matter, Markdown link, and anchor validation. | Implemented — `scripts/validate_docs.py`. |
| Backend | Dependency install, formatting/linting, type checks if configured, unit/API tests. | Implemented — Ruff lint, Ruff format check, pytest. |
| Frontend | Dependency install, lint/type checks, unit/component tests when configured. | Implemented — `npm ci`, ESLint, `tsc --noEmit`, Vitest, and the production build. |
| Database | Migration consistency checks, migration tests when migrations exist, and seed idempotency checks when seed tooling exists. | Implemented — migrations applied to an ephemeral PostgreSQL service, models compared against the resulting schema, constraints exercised, downgrade run, and each seed applied twice to confirm it is idempotent. |
| Containers | Compose topology validation and image build. | Implemented — backend and frontend images; the remaining service is added with its code. |
| Security hygiene | Secret scanning and dependency review where supported. | Not implemented. |

Do not add a CI check merely because it is common. Every check must be deterministic, documented, and fast enough to provide useful feedback. Add each pending check in the change that introduces the artifact it verifies.

## Implemented Workflow

`.github/workflows/pull-request.yml` defines five independent jobs:

| Job | Working directory | Commands |
| --- | --- | --- |
| `backend` | `backend/` | `python -m pip install -r requirements-dev.txt`, `python -m ruff check .`, `python -m ruff format --check .`, `python -m pytest` |
| `documentation` | repository root | `python -m pip install -r backend/requirements-dev.txt`, `python -m ruff check --config backend/pyproject.toml scripts/`, `python -m ruff format --check --config backend/pyproject.toml scripts/`, `python scripts/validate_docs.py` |
| `frontend` | `frontend/` | `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` |
| `database` | `backend/` | `python -m pip install -r requirements-dev.txt`, a database-reachability check, `python -m pytest tests/integration` |
| `containers` | repository root | `docker compose config -q`, `docker build -f docker/backend.Dockerfile .`, `docker build -f docker/frontend.Dockerfile .` |

The `backend`, `documentation`, and `database` jobs run on Python 3.14. The `frontend` job runs on
Node 24 and installs from `frontend/package-lock.json`. The `containers` job uses the Docker tooling
preinstalled on the runner and needs no language setup.

Every Python and Node verification command above also appears in the canonical
[local quality checks](../development/coding-standards.md#local-quality-checks), with one deliberate
difference: the canonical local set runs `python -m pytest -W error`, treating warnings as errors,
while CI runs `python -m pytest`. The local set is therefore the stricter of the two. The `pip
install` and `npm ci` steps are dependency installation, not checks.

### The frontend job

`npm ci` installs exactly the committed lockfile and fails when it disagrees with `package.json`,
which `npm install` would silently reconcile — so a dependency change that was never locked cannot
pass here.

`npm run build` is a check rather than a packaging step: it fails on a type error Next.js reports
that `tsc` alone does not, and on a route that cannot render. It reaches no API, because every
curriculum route is `force-dynamic` and nothing is fetched while prerendering. The job therefore
starts no service and needs no backend. `NEXT_TELEMETRY_DISABLED` is set for the same local-first
reason it is set in the image; see [Docker strategy](docker.md#the-frontend-service).

The frontend tests stub `fetch` and assert against the documented response envelope, so they verify
how the client handles the contract rather than whether a live backend honours it. Nothing yet reads
the real API from the frontend in CI, in the way the `database` job reads the curriculum endpoints
over HTTP for the backend.

The `database` job's integration tests are the one part of the suite the canonical local set does not
fully run: they skip unless `TEST_DATABASE_URL` names a reachable database, which needs a local
PostgreSQL. A contributor with Docker can run them with `docker compose up -d postgres` and a
disposable test database.

### The database job

The job runs an ephemeral `postgres:18-alpine` service container, created fresh for each run and
discarded with it, so migrations are always applied from an empty database and no developer's local
data is ever involved. `TEST_DATABASE_URL` points the tests at it.

Because the integration tests skip themselves when that database is unreachable, a failed service
container would otherwise leave the job green while verifying nothing. The job therefore opens a
connection in a separate step first and fails there if it cannot.

The tests apply every migration, compare the SQLAlchemy models against the resulting schema,
attempt the writes each documented constraint forbids, and downgrade back to empty. They also apply
each seed to that database and apply it a second time, which is where idempotency is
verified against real rows rather than a fake, and they run the whole local setup path — curriculum,
examination schedule, study goal — end to end against the bundled data files. They then build the
application through the real composition root against that same database and read the
[curriculum endpoints](../api/endpoints.md#curriculum-endpoints) over HTTP, so the query the API
actually issues is verified against seeded rows rather than against a fake repository. The
constraints they exercise are defined in
[database schema](../database/schema.md) and the testing requirements in
[database migrations](../database/migrations.md);
[ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md) records why they exist.

The `containers` job commands are not in the canonical local set, which covers the Python checks that
run without extra tooling. Container commands need a working Docker installation; run them locally
when Docker is available, per [Docker strategy](docker.md).

The `containers` job first ran on pull request #7 and passed, so the Compose topology and the backend
image build are verified in CI; the frontend image build joined it with the frontend application. It
has not been run locally: neither the change that introduced it nor the change that added the
frontend service had a Docker installation available, and CI remains the authoritative verification
for container checks. Note what the job does not cover — it validates and builds, but starts no
container, so the health checks and the services' runtime behavior are unverified. See
[Docker strategy](docker.md).

Properties that keep the workflow trustworthy:

- Every CI verification command is one a contributor can run locally, so a failure is reproducible offline. The `database` job's tests additionally need a PostgreSQL instance and `TEST_DATABASE_URL`.
- The jobs share no state, read no secrets, and publish no artifacts. Only the `database` job starts a service, and that service is an ephemeral container created and destroyed with the run.
- `permissions` is restricted to `contents: read`, and superseded runs on the same ref are cancelled.
- Documentation validation dependencies are pinned in `backend/requirements-dev.txt`, so the
  validator and the backend share one dependency source.

### The documentation job lints its own tool

`scripts/` sits outside `backend/`, so the Ruff configuration in `backend/pyproject.toml` is not
discovered from there. The documentation job therefore points Ruff at that configuration explicitly
and lints `scripts/validate_docs.py` before running it. The validator is held to the same lint and
formatting standards as backend code, under one shared configuration.

The canonical definition of these commands lives in
[local quality checks](../development/coding-standards.md#local-quality-checks). Run that set locally
from the repository root.

### Documentation validation scope

`scripts/validate_docs.py` checks what the documentation standards state mechanically. That document
owns the enumeration and its two deliberate exemptions; see
[mechanical validation](../development/documentation-standards.md#mechanical-validation).

It does not judge content. Duplicated or conflicting decisions, terminology drift, and missing ADRs
remain the responsibility of the `documentation-reviewer` agent and human review.

## Target Pipeline

The implemented workflow runs everything below, as five independent parallel jobs.

```text
Checkout source                                          # implemented
      ↓
Validate documentation, run backend checks/tests,
run frontend checks/tests, run migration checks,
and validate the container builds                        # implemented, in parallel
      ↓
Report pass/fail results                                 # implemented
```

Stages run in parallel when they have no shared state and use isolated test environments.

## Pull Request / Branch Policy

Current rules:

- Feature branches must pass CI before merging to `main`.
- All five jobs run on every pull request and every push to `main`, whatever the change touches.
- A failing check must be understood before merge, or merged only on an explicit project-owner
  decision. Because branch protection is not configured, this is a convention that reviewers uphold
  rather than a restriction GitHub enforces.
- Database changes require schema-documentation review, and run migration tests in the `database` job.
- Container and Compose changes are covered by the `containers` job, which validates the topology and
  builds the backend and frontend images.

## Test Data and Secrets

- CI must use synthetic/fixture data only.
- Never upload learner PDFs, test results, database volumes, local vector indexes, or Ollama model files as CI artifacts.
- Do not require real cloud provider credentials for ordinary tests.
- Use fake/mocked provider adapters for deterministic domain/application tests.
- Store future CI secrets only in the CI platform’s secret management, never in repository files.

## Database in CI

The `database` job implements these rules:

- Start an isolated PostgreSQL service/container. Implemented — an ephemeral `postgres:18-alpine`
  service, created and destroyed with each run.
- Apply migrations from an empty database state. Implemented.
- Run migration/application tests against that isolated database. Implemented.
- Do not connect CI to a developer's local Docker database or any personal learner data. Implemented
  — `TEST_DATABASE_URL` names only the service container, and it never falls back to `DATABASE_URL`.

## Container Build Policy

The `containers` job implements this policy for the backend and frontend images:

- Build images in CI to catch dependency/build failures.
- Avoid pushing images to a public registry until a deployment strategy is approved.
- Use `.dockerignore` to ensure private/generated local data cannot enter image build context.
- Do not attempt to download large Ollama models in normal CI.

## Future CD Requirements

Before enabling automatic deployment, define and approve:

- Staging and production environment configuration.
- Managed secrets and access controls.
- Database backup, migration, rollback/forward-recovery process.
- Resource-storage and vector-index persistence strategy.
- Monitoring, logs, and alerting.
- Cloud-provider privacy/cost policy.
- A safe release and rollback workflow.

Deployment is a product/operations decision, not an automatic result of having Docker Compose.

## AI-Assisted Change Rule

AI assistants may propose workflow files and CI commands, but they must not:

- Add cloud credentials or tokens to repository files.
- Disable safety checks simply to make a workflow pass.
- Add public image publication or deployment without explicit approval.
- Treat an untested generated workflow as production-ready.

## Definition of CI Readiness

A check joins CI only when all of the following hold for the area it covers:

- Dependency configuration for that area is committed.
- At least one deterministic test/check command is documented.
- `.env.example` and `.gitignore` prevent obvious secret/local-data leakage.
- The check runs without manual local state.

The backend foundation satisfied all four, which is why the workflow above exists. The frontend
satisfied them when it arrived: `frontend/package.json` and its lockfile are committed, five
documented commands run against them, `.gitignore` already excluded `node_modules/` and `.next/`, and
none of the checks needs a running service. Apply the same four conditions to each pending check in
the *CI Responsibilities* table before adding it.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-010: Deliver features through pull requests with automated gates](../adr/ADR-010-feature-delivery-workflow.md) — the decision this pipeline implements
- [Environments](environments.md)
- [Docker strategy](docker.md) — the images and topology the `containers` job validates
- [ADR-015: Build the frontend on Next.js and reach the API from the server](../adr/ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the frontend the `frontend` job checks
- [API endpoints](../api/endpoints.md) — the endpoints the `database` job reads over HTTP
- [Git workflow](../development/git-workflow.md)
- [Coding standards](../development/coding-standards.md)
- [Documentation standards](../development/documentation-standards.md) — the rules the documentation job enforces
- [Engineering AI workflow](../ai/engineering-ai.md)
- [Database migrations](../database/migrations.md) — the migrations the `database` job applies
