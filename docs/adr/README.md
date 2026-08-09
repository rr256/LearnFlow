---
title: Architecture Decision Records
status: approved
owner: architecture
last_updated: 2026-08-09
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

ADR decision files — `ADR-NNN-*.md` other than `ADR-000-template.md` — use the ADR status set: `proposed`, `accepted`, `superseded`, `rejected`. [Documentation standards](../development/documentation-standards.md#which-vocabulary-applies-by-path) defines both sets and resolves every path.

Two files in this directory are not decisions, so they are normal documentation files carrying normal-document statuses:

- `ADR-000-template.md` — a reusable format, status `template`.
- `README.md`, this file — navigation for the directory, status `approved`.

## Accepted ADRs

[ADR-001](ADR-001-clean-architecture.md) · [ADR-002](ADR-002-provider-pattern.md) · [ADR-003](ADR-003-postgresql-persistence.md) · [ADR-004](ADR-004-ollama-local-ai-provider.md) · [ADR-005](ADR-005-docker-compose-local-development.md) · [ADR-006](ADR-006-custom-agent-orchestration.md) · [ADR-007](ADR-007-documentation-and-adr-policy.md) · [ADR-008](ADR-008-assessment-and-mistake-evidence-model.md) · [ADR-009](ADR-009-configuration-naming-and-validation.md) · [ADR-010](ADR-010-feature-delivery-workflow.md) · [ADR-011](ADR-011-sqlalchemy-persistence-implementation.md) · [ADR-012](ADR-012-curriculum-seed-and-reconciliation.md) · [ADR-013](ADR-013-examination-schedule-and-study-goal.md) · [ADR-014](ADR-014-api-response-contract.md) · [ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md) · [ADR-016](ADR-016-learner-onboarding-api-contracts.md) · [ADR-017](ADR-017-topic-progress-api-and-schema.md) · [ADR-018](ADR-018-weekly-availability-slots.md) · [ADR-019](ADR-019-study-goal-planning-preferences.md) · [ADR-020](ADR-020-initial-study-plan-generation.md) · [ADR-021](ADR-021-plan-item-completion.md)

## Proposed ADRs

Drafted and awaiting project-owner acceptance. A proposed record states a direction that has been
decided but not yet accepted, so the code it describes may already exist while the record does not
yet bind.

- [ADR-022](ADR-022-plan-adaptation.md) — Adapt a study plan by rebuilding it around what happened.

A file name is a stable identifier and is not renamed once an ADR is accepted, so it may not match
the record's title. `ADR-016-learner-onboarding-api-contracts.md` is titled *Fix the Learner Setup
API Contracts*, because [terminology](../domain/terminology.md#naming-rules) settled that name after
the file was created.

The [architecture decision register](../architecture/decisions.md) maps each ADR to the decision it records.

## Related Documents

- [Project context](../00-project-context.md)
- [Architecture decision register](../architecture/decisions.md)
- [ADR template](ADR-000-template.md)
