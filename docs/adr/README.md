---
title: Architecture Decision Records
status: approved
owner: architecture
last_updated: 2026-07-29
related:
  - ../00-project-context.md
  - ADR-000-template.md
  - ../architecture/decisions.md
  - ../development/documentation-standards.md
---

# Architecture Decision Records

## Purpose

ADRs record significant, lasting technical or product-architecture decisions and their rationale.

## When to create an ADR

Create one for decisions that are costly to reverse or influence multiple modules: architecture style, persistent data strategy, public API versioning, major dependencies, security boundaries, and deployment topology.

## Naming

Use `ADR-NNN-short-title.md`, with zero-padded sequential numbering.

## Statuses

ADRs use the ADR status set — `proposed`, `accepted`, `superseded`, `rejected` — which is separate from the normal-document statuses used elsewhere under `docs/`. [Documentation standards](../development/documentation-standards.md) defines both sets.

`ADR-000-template.md` is the exception: it carries the normal-document status `template` because it is a reusable format, not a decision.

## Accepted ADRs

[ADR-001](ADR-001-clean-architecture.md) · [ADR-002](ADR-002-provider-pattern.md) · [ADR-003](ADR-003-postgresql-persistence.md) · [ADR-004](ADR-004-ollama-local-ai-provider.md) · [ADR-005](ADR-005-docker-compose-local-development.md) · [ADR-006](ADR-006-custom-agent-orchestration.md) · [ADR-007](ADR-007-documentation-and-adr-policy.md) · [ADR-008](ADR-008-assessment-and-mistake-evidence-model.md)

The [architecture decision register](../architecture/decisions.md) maps each ADR to the decision it records.

## Related Documents

- [Project context](../00-project-context.md)
- [Architecture decision register](../architecture/decisions.md)
- [ADR template](ADR-000-template.md)
