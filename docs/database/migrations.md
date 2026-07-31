---
title: LearnFlow Database Migrations
status: approved
owner: architecture-and-data
last_updated: 2026-07-31
related:
  - ../00-project-context.md
  - overview.md
  - schema.md
  - ../development/git-workflow.md
  - ../development/folder-structure.md
  - ../adr/ADR-011-sqlalchemy-persistence-implementation.md
  - ../deployment/environments.md
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

### Commands

Alembic is configured by `backend/alembic.ini`, with its environment in `backend/migrations/env.py`
and revisions in `backend/migrations/versions/`. Run from `backend/`:

```bash
python -m alembic upgrade head          # apply every pending migration
python -m alembic current               # show the applied revision
python -m alembic downgrade -1          # revert the most recent migration
python -m alembic upgrade head --sql    # print SQL without connecting
```

The target database comes from `DATABASE_URL` through the application's validated settings, so a
migration cannot be applied to a database the backend was never configured for, and no credential
lives in a committed file. `alembic.ini` has no `sqlalchemy.url`.
[Environments and configuration](../deployment/environments.md) is the authoritative catalogue for
that variable and for `TEST_DATABASE_URL`.

`--sql` needs no reachable database, which makes it the way to review generated DDL and to check a
migration on a machine without PostgreSQL installed.

Nothing applies migrations automatically. Neither application startup nor a container entrypoint
runs `alembic upgrade`; see [ADR-005](../adr/ADR-005-docker-compose-local-development.md).

## Migration Naming

Use Alembic's revision identifier plus a short, meaningful slug.

Examples:

```text
20260801_01_add_learner_and_study_goal_tables.py
20260801_02_add_topic_progress.py
20260815_01_add_external_test_results.py
```

These are illustrative, not applied. The applied revisions are listed below.

The slug describes the business/schema change, not a vague implementation action such as `update_models`.

Alembic generates a random hexadecimal identifier by default, so the dated form is supplied
explicitly when creating a revision:

```bash
python -m alembic revision --autogenerate --rev-id 20260801_01 -m "add learner tables"
```

The applied revisions are:

| Revision | Change |
| --- | --- |
| `20260731_01` | `create_curriculum_tables` — learning programs, curriculum versions, subjects, topics, and topic relationships. |

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

`backend/tests/integration/` automates the first, third, and fifth of these: it applies the
migrations to an empty database, compares the models against the resulting schema, attempts the
writes each documented constraint forbids, and downgrades back to empty. The curriculum seed is
exercised against the same database, including a repeat run that must write nothing. The tests read
`TEST_DATABASE_URL` and skip when it is unset, so they never touch development or learner data;
[environments and configuration](../deployment/environments.md) records why it has no fallback. The
CI `database` job supplies an ephemeral PostgreSQL service and fails if that database is
unreachable, so the checks cannot pass by silently skipping. See
[CI/CD strategy](../deployment/ci-cd.md).

Testing against representative existing data remains a manual step. The seed tests populate a
database with reference data, but no learner-owned data exists yet to migrate against.

## Seed Data vs Migrations

Schema migrations create and evolve database structure. They should not become a general-purpose content-loading mechanism.

The curated GATE CSE curriculum is reference data. Manage it through explicit, idempotent seed/import tooling that:

- Identifies the target learning-program and curriculum version.
- Can be run repeatedly without duplicating records.
- Is versioned and documented.
- Does not overwrite learner progress.

A migration may create minimal required system records only when the schema genuinely requires them.

### The curriculum seed

`backend/scripts/seed_curriculum.py` implements the rules above for the curriculum area. Run it from
`backend/`, after the migrations:

```bash
python -m scripts.seed_curriculum             # the bundled GATE CSE curriculum
python -m scripts.seed_curriculum --dry-run   # report what would change, then roll back
python -m scripts.seed_curriculum --file <path>
```

The curriculum itself is data, not code: `backend/scripts/gate_cse_curriculum.json` holds the
transcribed GATE CSE syllabus and records its official source and transcription rules in a
`$comment` block. Loading a different program or a later syllabus is a new file, not a code change.

Repeatability comes from matching every record on a natural key and writing only what differs:

| Record | Natural key | Enforced by |
| --- | --- | --- |
| Learning program | `code` | `uq_learning_programs_code` |
| Curriculum version | `(learning_program_id, version_label)` | `uq_curriculum_versions_learning_program_id_version_label` |
| Subject | `(curriculum_version_id, code)` | `uq_subjects_curriculum_version_id_code` |
| Topic | `(subject_id, parent_topic_id, name)` | `uq_topics_subject_id_parent_topic_id_name` |
| Topic | `(subject_id, code)`, when the seed gives a topic a code | The seed only — see below |
| Topic relationship | `(source_topic_id, target_topic_id, relationship_type)` | `pk_topic_relationships` |

Every key above maps to a database constraint except the topic `code` key. `topics.code` is nullable
and carries no uniqueness constraint, so that match is enforced by the seed alone: it rejects a file
that reuses a topic code within a subject, but nothing stops another writer from creating a duplicate.
Whether `(subject_id, code)` should become a database constraint is an open schema question, not a
guarantee this seed already provides.

A second run of an unchanged file writes nothing and reports every record as unchanged.

**The seed never deletes.** A subject or topic dropped from the source file keeps its row, because
learner progress, plans, and assessment evidence reference those identifiers. Dropped subjects move
behind the seeded ones so the seeded positions stay contiguous. Removing curriculum a learner has
used is a deliberate, separately approved change, not a side effect of editing a data file.

A topic without a `code` that is renamed in the source reads as a new topic rather than a rename,
since nothing distinguishes the two. Give a topic a `code` when its name may need to change.

The seed refuses to activate a second curriculum version while another is active, naming both, rather
than letting the partial unique index from
[ADR-011](../adr/ADR-011-sqlalchemy-persistence-implementation.md) surface as an integrity error.

The target database is `DATABASE_URL`, read through the application's validated settings, and the
whole run is one transaction that commits only on success.

## Environment Workflow

### Local development

1. Start PostgreSQL through the documented Docker environment: `docker compose up -d postgres`.
2. Apply the current Alembic migration head: `cd backend && python -m alembic upgrade head`.
3. Load or refresh the curated curriculum: `cd backend && python -m scripts.seed_curriculum`. It is
   safe to repeat; see [the curriculum seed](#the-curriculum-seed).
4. Run application and migration tests. The migration tests need `TEST_DATABASE_URL` pointing at a
   separate disposable database, never the one from step 1.

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
- [ADR-003: Use PostgreSQL for structured persistence](../adr/ADR-003-postgresql-persistence.md) — establishes Alembic as the migration workflow
- [ADR-005: Use Docker Compose for local development](../adr/ADR-005-docker-compose-local-development.md) — requires migrations to stay an explicit step, not a startup side effect
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](../adr/ADR-011-sqlalchemy-persistence-implementation.md) — why the schema is migrated one area at a time
- [CI/CD strategy](../deployment/ci-cd.md) — the `database` job that runs these migrations on every pull request
- [Environments and configuration](../deployment/environments.md) — the authoritative catalogue for `DATABASE_URL` and `TEST_DATABASE_URL`
- [Database overview](overview.md)
- [Database schema](schema.md)
- [Repository and folder structure](../development/folder-structure.md) — where the seed tooling lives
- [Git workflow](../development/git-workflow.md)
- [Architecture Decision Register](../architecture/decisions.md)
