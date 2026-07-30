---
title: LearnFlow CI/CD Strategy
status: approved
owner: development-and-operations
last_updated: 2026-07-30
related:
  - ../00-project-context.md
  - environments.md
  - ../development/git-workflow.md
  - ../development/coding-standards.md
  - ../development/documentation-standards.md
  - docker.md
  - ../adr/ADR-010-feature-delivery-workflow.md
---

# LearnFlow CI/CD Strategy

## Purpose

Define how LearnFlow automates verification and what remains deferred.

The MVP does not require public deployment. Continuous integration protects code and documentation quality; continuous deployment remains deferred until a hosted environment is approved.

## Current Decision

### Continuous Integration

CI configuration is implemented and covers the backend, the documentation set, and the container
build. All three jobs run on every pull request targeting `main` and on every push to `main`; the
workflow applies no path filters, so a documentation-only change runs the backend and container jobs
too. See [Implemented Workflow](#implemented-workflow) below.

Two limits apply to the current state:

- **Frontend and database checks are not implemented.** No `frontend/` application or migration exists
  to check; see the *CI Responsibilities* table below.
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
| Frontend | Dependency install, lint/type checks, unit/component tests when configured. | Not implemented — no `frontend/` exists. |
| Database | Migration consistency checks and migration tests when migrations exist. | Not implemented — no migrations exist. |
| Containers | Compose topology validation and image build. | Implemented — backend image; the other services are added with their code. |
| Security hygiene | Secret scanning and dependency review where supported. | Not implemented. |

Do not add a CI check merely because it is common. Every check must be deterministic, documented, and fast enough to provide useful feedback. Add each pending check in the change that introduces the artifact it verifies.

## Implemented Workflow

`.github/workflows/pull-request.yml` defines three independent jobs:

| Job | Working directory | Commands |
| --- | --- | --- |
| `backend` | `backend/` | `python -m pip install -r requirements-dev.txt`, `python -m ruff check .`, `python -m ruff format --check .`, `python -m pytest` |
| `documentation` | repository root | `python -m pip install -r backend/requirements-dev.txt`, `python -m ruff check --config backend/pyproject.toml scripts/`, `python -m ruff format --check --config backend/pyproject.toml scripts/`, `python scripts/validate_docs.py` |
| `containers` | repository root | `docker compose config -q`, `docker build -f docker/backend.Dockerfile .` |

The `backend` and `documentation` jobs run on Python 3.14. The `containers` job uses the Docker
tooling preinstalled on the runner and needs no Python setup.

Every Python verification command above also appears in the canonical
[local quality checks](../development/coding-standards.md#local-quality-checks), with one deliberate
difference: the canonical local set runs `python -m pytest -W error`, treating warnings as errors,
while CI runs `python -m pytest`. The local set is therefore the stricter of the two. The `pip
install` steps are dependency installation, not checks.

The `containers` job commands are not in the canonical local set, which covers the Python checks that
run without extra tooling. Container commands need a working Docker installation; run them locally
when Docker is available, per [Docker strategy](docker.md).

**No container command has been executed anywhere yet.** The change that introduced this job was
prepared on a machine without Docker, so neither `docker compose config -q` nor the backend image
build has run locally. The `containers` job on the pull request introducing it is their first
execution. Until that run passes, treat the Compose file and Dockerfile as written but unbuilt.

Properties that keep the workflow trustworthy:

- Every CI verification command is one a contributor can run locally, so a failure is reproducible offline.
- The jobs share no state, start no services, read no secrets, and publish no artifacts.
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

The implemented workflow runs the first two stages below as three independent parallel jobs. The
remaining stages describe the intended shape of the pipeline as the artifacts they check are added;
they do not exist today.

```text
Checkout source                                          # implemented
      ↓
Validate documentation, run backend checks/tests,
and validate the container build                         # implemented, in parallel
      ↓
Run frontend checks and tests                            # pending a frontend
      ↓
Run migration/integration checks when applicable         # pending migrations
      ↓
Report pass/fail results                                 # implemented
```

Stages run in parallel when they have no shared state and use isolated test environments.

## Pull Request / Branch Policy

Current rules:

- Feature branches must pass CI before merging to `main`.
- All three jobs run on every pull request and every push to `main`, whatever the change touches.
- A failing check must be understood before merge, or merged only on an explicit project-owner
  decision. Because branch protection is not configured, this is a convention that reviewers uphold
  rather than a restriction GitHub enforces.
- Database changes require schema-documentation review.
- Container and Compose changes are covered by the `containers` job, which validates the topology and
  builds the backend image.

Rules that take effect when the corresponding checks exist:

- Database changes run migration tests.

## Test Data and Secrets

- CI must use synthetic/fixture data only.
- Never upload learner PDFs, test results, database volumes, local vector indexes, or Ollama model files as CI artifacts.
- Do not require real cloud provider credentials for ordinary tests.
- Use fake/mocked provider adapters for deterministic domain/application tests.
- Store future CI secrets only in the CI platform’s secret management, never in repository files.

## Database in CI

When database tests are introduced:

- Start an isolated PostgreSQL service/container.
- Apply migrations from an empty database state.
- Run migration/application tests against that isolated database.
- Do not connect CI to a developer’s local Docker database or any personal learner data.

## Container Build Policy

The `containers` job implements this policy for the backend image:

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

The backend foundation satisfied all four, which is why the workflow above exists. Apply the same four
conditions to each pending check in the *CI Responsibilities* table before adding it.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-010: Deliver features through pull requests with automated gates](../adr/ADR-010-feature-delivery-workflow.md) — the decision this pipeline implements
- [Environments](environments.md)
- [Docker strategy](docker.md) — the images and topology the `containers` job validates
- [Git workflow](../development/git-workflow.md)
- [Coding standards](../development/coding-standards.md)
- [Documentation standards](../development/documentation-standards.md) — the rules the documentation job enforces
- [Engineering AI workflow](../ai/engineering-ai.md)
- [Database migrations](../database/migrations.md)
