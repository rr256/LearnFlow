---
title: LearnFlow Database Migrations
status: approved
owner: architecture-and-data
last_updated: 2026-08-01
related:
  - ../00-project-context.md
  - overview.md
  - schema.md
  - ../development/git-workflow.md
  - ../development/folder-structure.md
  - ../adr/ADR-011-sqlalchemy-persistence-implementation.md
  - ../adr/ADR-012-curriculum-seed-and-reconciliation.md
  - ../adr/ADR-013-examination-schedule-and-study-goal.md
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
| `20260731_02` | `add_topic_code_unique_constraint` — `uq_topics_subject_id_code`, so a topic code identifies one topic within its subject. Additive; safe on populated tables. |
| `20260801_01` | `create_examination_schedule_and_learner_goal_tables` — examination schedules and their dated periods, plus the first two learner-planning tables, `learners` and `study_goals`. Creates four empty tables; adds nothing to an existing one. |

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
writes each documented constraint forbids, and downgrades back to empty. Both seeds are exercised
against the same database, each including a repeat run that must write nothing, and the whole local
setup path — curriculum, schedule, goal — runs end to end against the bundled data files. The tests read
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

The rows this seed writes are what the curriculum read endpoints CUR-001 to CUR-003 serve, so a
re-seeded correction reaches a client on its next request with no further step. See
[API endpoints](../api/endpoints.md#curriculum-endpoints).

#### Source of the bundled GATE CSE curriculum

| | |
| --- | --- |
| Learning program | `gate-cse` — GATE Computer Science and Information Technology |
| Curriculum version | `2027`, seeded `active` |
| Organising institute | IIT Madras |
| CS sections 1–10 | <https://gate2027.iitm.ac.in/static/doc/GATE2027_Syllabus/CS_GATE2027_Syllabus.pdf> |
| General Aptitude | <https://gate2027.iitm.ac.in/static/doc/GATE2027_Syllabus/GA_GATE2027_Syllabus.pdf> |

General Aptitude is published separately but is part of the CS paper, so it is seeded as an eleventh
subject after the ten numbered CS sections. Both URLs are also stored in the version's
`source_reference` column, so a seeded curriculum can be traced to its source from the database alone.

The transcription rules — one subject per official section, topics split at the delimiter each
section itself uses, wording unchanged — are recorded in the data file's `$comment` block so the file
stays checkable against the two PDFs. The `$comment` block also records what changed from the GATE
2026 syllabus and the two spacing artefacts reproduced from the 2027 source rather than tidied away.

A later syllabus year is a new data file with its own `version_label`. Because the seed refuses to
activate a second version while another is active, the order is fixed — retire first, then activate:

1. Re-seed the current year's file with `"version_status": "retired"`. Nothing else in it changes,
   and its subjects and topics are rewritten as unchanged.
2. Seed the new year's file as `"version_status": "active"`.

Running step 2 first is refused, naming both versions. There is no single-run switchover, and no
command retires a version that no seed file names.

This path has not been exercised — GATE CSE 2027 is the only curriculum version that exists, and it
is the seeded active one. Treat the sequence above as the supported route, not as a rehearsed
procedure.

Repeatability comes from matching every record on a natural key and writing only what differs:

| Record | Natural key | Enforced by |
| --- | --- | --- |
| Learning program | `code` | `uq_learning_programs_code` |
| Curriculum version | `(learning_program_id, version_label)` | `uq_curriculum_versions_learning_program_id_version_label` |
| Subject | `(curriculum_version_id, code)` | `uq_subjects_curriculum_version_id_code` |
| Topic | `(subject_id, code)`, when the topic carries a code | `uq_topics_subject_id_code` |
| Topic | `(subject_id, parent_topic_id, name)` otherwise | `uq_topics_subject_id_parent_topic_id_name` |
| Topic relationship | `(source_topic_id, target_topic_id, relationship_type)` | `pk_topic_relationships` |

Every key the seed matches on is enforced by the database, so the seed and the schema cannot disagree
about what identifies a record. Note that the two topic rules have different scopes: a name is unique
among siblings, so the same name may appear under two parents, while a code is unique across the
whole subject at any depth. The seed validates a file at both scopes before writing.

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

#### Re-ordering subjects

`(curriculum_version_id, position)` is unique and PostgreSQL checks it per statement, not at commit,
so two subjects trading places would collide midway through the update even though the final state is
valid.

When any subject's position changes, the seed therefore moves every subject of that version out of
the positive range first — `position` becomes `-position - 1`, which is injective and always negative
— flushes, and then assigns the final positions. The order of the updates that follow stops mattering
because every target position is free.

A subject whose position is unchanged is still rewritten during this step. Vacating moved it too, so
skipping it would leave it parked outside the range. It is still reported as unchanged, because its
final state is what was already stored.

This is a workaround for a per-statement constraint check, not a schema decision; the alternative
would be a deferrable constraint, which
[schema.md](schema.md#topics) does not specify.

### The examination schedule seed

`backend/scripts/seed_examination_schedule.py` applies the same rules to the examination calendar an
examining body publishes. Run it from `backend/`, after the migrations **and after the curriculum
seed** — a schedule belongs to a learning program the curriculum seed creates, and seeding one first
is refused with a message naming the command to run:

```bash
python -m scripts.seed_examination_schedule             # the bundled GATE 2027 schedule
python -m scripts.seed_examination_schedule --dry-run   # report what would change, then roll back
python -m scripts.seed_examination_schedule --file <path>
```

The schedule is data, not code: `backend/scripts/gate_cse_examination_schedule.json` holds the
published GATE 2027 dates and records its official source, its transcription rules, and its one
inference in a `$comment` block. A different examination cycle, or another program's calendar, is a
new file rather than a code change.

#### Source of the bundled GATE 2027 schedule

| | |
| --- | --- |
| Learning program | `gate-cse` |
| Cycle | `2027`, seeded `provisional` |
| Organising body | IIT Madras |
| Source | <https://gate2027.iitm.ac.in/> |
| Read on | 2026-08-01, verified against the official source |

| Period | Dates |
| --- | --- |
| Registration | 14 August 2026 – 21 September 2026 |
| Late registration | 22 September 2026 – 30 September 2026 |
| Examination | 6–7, 13–14, and 20–21 February 2027, as three separate periods |
| Results | 19 March 2027 |

**These dates are liable to change.** The source says so, which is why the schedule is seeded
`provisional` rather than `confirmed`. Re-seed with `"schedule_status": "confirmed"` once the
organising institute confirms them.

The source publishes a *closing* date for late registration rather than an opening one, so the period
is recorded as beginning the day after regular registration closes. That is the file's one inference,
and its `$comment` block says so. The day the Computer Science paper itself is sat is not published;
no period names it.

Repeatability comes from the same match-then-compare rule as the curriculum:

| Record | Natural key | Enforced by |
| --- | --- | --- |
| Examination schedule | `(learning_program_id, cycle_label)` | `uq_examination_schedules_learning_program_id_cycle_label` |
| Examination period | `(examination_schedule_id, period_type, starts_on)` | `uq_examination_periods_schedule_id_period_type_starts_on` |

A period is keyed on its start date because a cycle holds three `examination` periods. A corrected
*end* date therefore updates a period in place, while a sitting moved to a different *day* reads as a
new period alongside the old one. **The seed never deletes**, so a schedule revised repeatedly
accumulates superseded periods; retiring them is a deliberate, separately approved change, exactly as
for curriculum.

### Setting the local learner's study goal

`backend/scripts/set_study_goal.py` binds the local learner to a curriculum and an examination goal.
Run it from `backend/`, after both seeds:

```bash
python -m scripts.set_study_goal                          # GATE CSE, GATE 2027
python -m scripts.set_study_goal --display-name "Asha"
python -m scripts.set_study_goal --no-examination --target-date 2027-06-30
python -m scripts.set_study_goal --dry-run
```

It creates the local learner on first run, with the timezone from `APP_DEFAULT_TIMEZONE`, and leaves
an existing learner untouched afterwards — renaming a learner is a profile change with its own
workflow. It is idempotent: it matches the learner's active goal for the program, writes only what
differs, and never rewrites a goal that is paused, completed, or archived.

The goal stores a *reference* to the examination schedule, never a copy of its dates, so a re-seeded
correction reaches it without a learner-data migration. The examination window it reports spans the
first and last published sitting days. See
[ADR-013](../adr/ADR-013-examination-schedule-and-study-goal.md).

## Environment Workflow

### Local development

1. Start PostgreSQL through the documented Docker environment: `docker compose up -d postgres`.
2. Apply the current Alembic migration head: `cd backend && python -m alembic upgrade head`.
3. Load or refresh the curated curriculum: `cd backend && python -m scripts.seed_curriculum`. It is
   safe to repeat; see [the curriculum seed](#the-curriculum-seed).
4. Load or refresh the published examination schedule: `python -m scripts.seed_examination_schedule`.
   Also safe to repeat; see [the examination schedule seed](#the-examination-schedule-seed).
5. Set the learner's goal: `python -m scripts.set_study_goal`. Safe to repeat.
6. Run application and migration tests. The migration tests need `TEST_DATABASE_URL` pointing at a
   separate disposable database, never the one from step 1.

Each step refuses to run ahead of its predecessor, naming the command to run first.

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
- [ADR-012: Load curriculum as reconciled reference data from a versioned file](../adr/ADR-012-curriculum-seed-and-reconciliation.md) — the durable rationale for the seed's matching, update, and never-delete rules
- [ADR-013: Model an examination period as a published window of reference data](../adr/ADR-013-examination-schedule-and-study-goal.md) — the rationale for the examination schedule seed and the study goal it feeds
- [CI/CD strategy](../deployment/ci-cd.md) — the `database` job that runs these migrations on every pull request
- [Environments and configuration](../deployment/environments.md) — the authoritative catalogue for `DATABASE_URL` and `TEST_DATABASE_URL`
- [API endpoints](../api/endpoints.md) — the curriculum endpoints that read what the curriculum seed writes
- [Database overview](overview.md)
- [Database schema](schema.md)
- [Repository and folder structure](../development/folder-structure.md) — where the seed tooling lives
- [Git workflow](../development/git-workflow.md)
- [Architecture Decision Register](../architecture/decisions.md)
