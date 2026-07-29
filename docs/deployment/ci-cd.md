---
title: LearnFlow CI/CD Strategy
status: approved
owner: development-and-operations
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - environments.md
  - ../development/git-workflow.md
  - ../development/coding-standards.md
---

# LearnFlow CI/CD Strategy

## Purpose

Define how LearnFlow will automate verification now and prepare for safe delivery later.

The MVP does not require public deployment. Continuous integration is introduced to protect code/documentation quality; continuous deployment remains deferred until a hosted environment is approved.

## Current Decision

### Continuous Integration

Add CI once the backend/frontend scaffolds and test commands exist. CI runs on pull requests and relevant pushes to `main`.

### Continuous Deployment

Do not deploy publicly during the local-first MVP. Future deployment requires separate staging/production decisions, secrets, backup/recovery plans, and an ADR where appropriate.

## Initial CI Responsibilities

The first CI workflow should verify only stable, repeatable checks:

| Area | Expected check |
| --- | --- |
| Documentation | Markdown/link/front-matter validation when tooling is added. |
| Backend | Dependency install, formatting/linting, type checks if configured, unit/API tests. |
| Frontend | Dependency install, lint/type checks, unit/component tests when configured. |
| Database | Migration consistency checks and migration tests when migrations exist. |
| Containers | Dockerfile/Compose build validation when Docker files exist. |
| Security hygiene | Secret scanning and dependency review where supported. |

Do not add a CI check merely because it is common. Every check must be deterministic, documented, and fast enough to provide useful feedback.

## Pipeline Stages

```text
Checkout source
      ↓
Validate documentation/configuration
      ↓
Run backend checks and tests
      ↓
Run frontend checks and tests
      ↓
Run migration/integration checks when applicable
      ↓
Build container images when Docker artifacts exist
      ↓
Report pass/fail results
```

Stages may run in parallel when they have no shared state and use isolated test environments.

## Pull Request / Branch Policy

- Feature branches should pass relevant CI checks before merging to `main`.
- Documentation-only changes run documentation checks once available.
- Database changes run migration tests and require schema-documentation review.
- Infrastructure/provider changes run relevant Docker/configuration checks.
- Failing CI blocks merge until the failure is understood or an explicit project-owner decision is made.

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

When Dockerfiles and `compose.yaml` exist:

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

Add the first CI workflow when all of the following exist:

- Backend and/or frontend dependency configuration is committed.
- At least one deterministic test/check command is documented.
- `.env.example` and `.gitignore` prevent obvious secret/local-data leakage.
- The project can run checks without manual local state.

## Related Documents

- [Project context](../00-project-context.md)
- [Environments](environments.md)
- [Docker strategy](docker.md)
- [Git workflow](../development/git-workflow.md)
- [Coding standards](../development/coding-standards.md)
- [Database migrations](../database/migrations.md)
