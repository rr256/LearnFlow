---
title: LearnFlow Database Migrations
status: approved
owner: architecture-and-data
last_updated: 2026-07-28
related:
  - ../00-project-context.md
  - overview.md
  - schema.md
  - ../development/git-workflow.md
---

# LearnFlow Database Migrations

## Purpose

Define how LearnFlow changes its PostgreSQL schema safely, reproducibly, and with clear history.

## Decision

LearnFlow will use **Alembic** with SQLAlchemy for versioned database migrations.

No developer, AI assistant, or application startup process may silently alter the schema outside the migration workflow.

## Principles

- Every schema change is represented by a reviewed migration file.
- A migration must match an updated `docs/database/schema.md` when it changes the documented logical model.
- Migrations are source-controlled and applied in order.
- Learner progress, assessment evidence, curriculum history, and resources are valuable data; destructive changes require explicit planning.
- Automatic migration generation is a starting point for review, not proof that a migration is correct.

## Migration Lifecycle

```text
Approved schema/documentation change
        ↓
Update ORM/persistence mappings
        ↓
Generate or write Alembic migration
        ↓
Review generated SQL and upgrade/downgrade behavior
        ↓
Test against a fresh database and representative existing data
        ↓
Commit schema docs + migration + affected code together
        ↓
Apply through documented environment workflow
```

## Required Tooling

- SQLAlchemy for persistence mappings.
- Alembic for migration generation, version tracking, upgrade, and downgrade commands.
- PostgreSQL as the target database.

The exact command wrappers may be added later, but migrations must remain standard Alembic revisions inside the backend repository.

## Migration Naming

Use Alembic's revision identifier plus a short, meaningful slug.

Examples:

```text
20260728_01_create_curriculum_tables.py
20260728_02_add_topic_progress.py
20260728_03_add_external_test_results.py
```

The slug describes the business/schema change, not a vague implementation action such as `update_models`.

## What Requires a Migration

Create a migration for changes including:

- Creating, renaming, or removing tables.
- Adding, removing, or renaming columns.
- Changing column types, nullability, defaults, constraints, or indexes.
- Adding/changing enum values or controlled database values.
- Adding/changing foreign keys, unique keys, or check constraints.
- Required data backfills or transformations.

The following usually do not require a migration:

- Pure application validation that has no schema impact.
- Query or repository refactoring that leaves schema behavior unchanged.
- Documentation-only clarifications.

## Schema-Change Rules

### Additive Changes First

Prefer safe additive evolution:

```text
Add nullable column or new table
→ deploy/backfill data
→ update application reads/writes
→ make stricter only after data is valid
```

Do not add a non-null column to a populated table without a safe default, backfill, or staged migration plan.

### Renames and Replacements

Do not treat a rename as “drop old column, add new column” when learner data exists.

Use a staged approach:

1. Add the new column/table.
2. Backfill from existing data.
3. Update application reads/writes.
4. Verify data.
5. Remove old data only in a later, explicitly approved migration.

### Destructive Changes

Dropping data, narrowing types, or changing meaning requires:

- Clear justification in the migration and related documentation.
- A backup/recovery plan.
- A data-migration/backfill plan where applicable.
- An ADR when the change is architecturally consequential.

Never delete learner progress, quiz attempts, external test results, or source-resource metadata simply to simplify the schema.

## Upgrade and Downgrade Policy

- Every migration should provide a downgrade when it is safe and meaningful.
- For migrations that transform or delete data, a true downgrade may be impossible; document this clearly in the migration and release notes.
- In shared or production-like environments, prefer a forward corrective migration over casually running downgrades.
- Test both `upgrade` and safe `downgrade` paths during early local development when practical.

## Testing Requirements

Before accepting a migration:

- [ ] Run it against an empty PostgreSQL database.
- [ ] Run it against representative existing data when modifying populated tables.
- [ ] Verify keys, constraints, defaults, and indexes.
- [ ] Verify the application can start and perform the affected use cases.
- [ ] Verify rollback/forward-correction behavior as applicable.
- [ ] Ensure `docs/database/schema.md` reflects the resulting schema.

## Seed Data vs Migrations

Schema migrations create and evolve database structure. They should not become a general-purpose content-loading mechanism.

The curated GATE CSE curriculum is reference data. Manage it through explicit, idempotent seed/import tooling that:

- Identifies the target learning-program and curriculum version.
- Can be run repeatedly without duplicating records.
- Is versioned and documented.
- Does not overwrite learner progress.

A migration may create minimal required system records only when the schema genuinely requires them.

## Environment Workflow

### Local development

1. Start PostgreSQL through the documented Docker environment.
2. Apply the current Alembic migration head.
3. Load/update approved curriculum seed data when required.
4. Run application and migration tests.

### Future shared/cloud environments

- Take a verified backup before consequential changes.
- Apply migrations as a controlled deployment step, not from arbitrary developer machines.
- Record the deployed migration revision.
- Monitor failures and retain a forward-recovery path.

## AI-Assisted Change Rules

An AI assistant may propose or generate a migration, but it must not:

- Apply a destructive migration without explicit user approval.
- Invent schema changes that do not trace to a requirement or approved design.
- Assume autogenerated Alembic output is correct without review.
- Modify a migration that has already been shared/applied; create a new migration instead.

## Related Documents

- [Project context](../00-project-context.md)
- [Database overview](overview.md)
- [Database schema](schema.md)
- [Git workflow](../development/git-workflow.md)
- [Architecture Decision Register](../architecture/decisions.md)
