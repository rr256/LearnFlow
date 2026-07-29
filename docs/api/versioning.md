---
title: LearnFlow API Versioning
status: approved
owner: architecture-and-api
last_updated: 2026-07-28
related:
  - ../00-project-context.md
  - conventions.md
  - endpoints.md
  - ../development/git-workflow.md
---

# LearnFlow API Versioning

## Purpose

Define how LearnFlow evolves its HTTP API without silently breaking frontend clients, future mobile clients, or integrations.

## Decision

Public application endpoints use a path-based major version:

```text
/api/v1/
```

The initial API is version 1. A new major version is introduced only for intentional breaking changes.

## Compatible Changes Within a Major Version

The following may be added to `/api/v1` without creating `/api/v2`:

- New endpoints.
- New optional request fields.
- New optional response fields.
- New filter/sort options that do not change existing defaults.
- Performance improvements that preserve documented behavior.
- Additional enum values only when existing clients can handle them safely; otherwise use a versioned change.

## Breaking Changes

The following require a new major API version or a documented, staged compatibility strategy:

- Removing or renaming an endpoint.
- Removing or renaming a request/response field.
- Changing a field's meaning or data type.
- Making an optional request field required.
- Changing default behavior in a way that changes existing client results.
- Changing authentication/authorization behavior incompatibly.
- Changing error-envelope shape or stable error codes incompatibly.

## Deprecation Process

Before removing a public API capability:

1. Mark it as deprecated in endpoint documentation and API schemas.
2. Provide the supported replacement.
3. Keep the old capability available for a defined transition period when external clients exist.
4. Add warnings/telemetry where appropriate.
5. Remove it only in a later major version or according to an explicitly approved migration plan.

For the initial local MVP, the transition period may be short because the frontend and backend evolve together. The documentation requirement still applies.

## Version Boundaries

- API versioning applies to HTTP contracts, not database schemas.
- Database schema changes use Alembic migrations.
- Internal application interfaces can evolve through normal code review and tests; do not expose them as public API contracts.
- Provider interfaces are internal architecture contracts, not versioned HTTP endpoints.

## Client Expectations

- The frontend targets one explicit API major version.
- Clients must ignore unknown optional response fields.
- Clients must not rely on undocumented fields, ordering, provider names, filesystem paths, or internal error text.
- Clients must use documented enum values and be prepared for permitted future values where the API contract specifies extensibility.

## Documentation Requirements

When an API change is made:

1. Update `docs/api/endpoints.md`.
2. Update API schemas and automated contract tests.
3. Update `docs/api/conventions.md` if a cross-cutting convention changes.
4. Create an ADR for a major compatibility strategy or a new API version.
5. Update frontend clients in the same change where the MVP requires synchronized changes.

## Related Documents

- [Project context](../00-project-context.md)
- [API conventions](conventions.md)
- [API endpoint catalog](endpoints.md)
- [Database migrations](../database/migrations.md)
- [Git workflow](../development/git-workflow.md)
