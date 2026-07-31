---
title: "ADR-011: Implement PostgreSQL Persistence Synchronously and Migrate Per Milestone"
status: accepted
owner: architecture-and-data
last_updated: 2026-07-31
related:
  - ../00-project-context.md
  - ADR-003-postgresql-persistence.md
  - ADR-005-docker-compose-local-development.md
  - ADR-009-configuration-naming-and-validation.md
  - ../database/schema.md
  - ../database/migrations.md
  - ../deployment/environments.md
  - ../deployment/ci-cd.md
  - ../architecture/decisions.md
---

# ADR-011: Implement PostgreSQL Persistence Synchronously and Migrate Per Milestone

## Status

Accepted — 2026-07-31

## Context

[ADR-003](ADR-003-postgresql-persistence.md) selected PostgreSQL, SQLAlchemy, and Alembic. It did
not decide three things that the first line of persistence code cannot avoid:

1. **Which driver, and synchronous or asynchronous SQLAlchemy.** No document named a driver, and no
   document chose an execution model. The choice shapes every repository, every use case that calls
   one, and every test fixture, so it is expensive to revisit once repositories exist.
2. **How much of the schema the first migration creates.** `database/schema.md` is approved in full
   and describes twenty-seven tables across six areas. Milestone 1 needs the curriculum hierarchy
   and nothing else.
3. **Two either/or choices `schema.md` deliberately left open** — whether enumerated values become
   PostgreSQL enums or validated text, and whether "at most one active curriculum version per
   program" is enforced by a partial unique index or by application workflow.

`schema.md` also carries an *Implementation Review Required* gate stating that the schema is
reviewed before the first migration. This record is part of discharging that gate for the curriculum
area.

## Decision

### Synchronous SQLAlchemy with psycopg 3

Repositories use `sqlalchemy.orm.Session`, not `AsyncSession`. The driver is psycopg 3, installed as
`psycopg[binary]` so contributors need no local libpq or C toolchain.

FastAPI runs synchronous dependencies in a worker threadpool, so synchronous persistence does not
block the event loop. A local, single-learner MVP has no concurrency pressure that asynchronous
database access would relieve, and Alembic runs a synchronous engine natively.

### The first migration creates the curriculum area only

`20260731_01_create_curriculum_tables` creates `learning_programs`, `curriculum_versions`,
`subjects`, `topics`, and `topic_relationships`. Learner planning, progress, resource, and
assessment tables arrive in the migration belonging to the milestone that uses them.

A table created before the code that reads it fixes decisions — a `day_of_week` numbering
convention, a default learner timezone, numeric precision for scores — that no requirement has yet
constrained. `schema.md` remains the approved target for all six areas; this decision concerns
ordering, not scope.

### Controlled values are validated text, not PostgreSQL enums

`curriculum_versions.status` and `topic_relationships.relationship_type` are `text` guarded by a
`CHECK` constraint. Adding a value stays an ordinary constraint change rather than an `ALTER TYPE`,
and the stored value stays readable. `schema.md` permits either form and keeps the API/domain
vocabulary authoritative either way.

### One active curriculum version per program is enforced by the database

A partial unique index on `learning_program_id WHERE status = 'active'` — the stricter of the two
options `schema.md` allows. Two active versions would make "the current curriculum" ambiguous for
every learner planning against it, and an application-only rule cannot survive a seed script or a
manual correction.

### Supporting implementation choices

| Choice | Value | Reason |
| --- | --- | --- |
| Identifier generation | Application-side `uuid4` | An entity carries its identity before it is flushed, so an object graph can be assembled in one unit of work. |
| Topic name uniqueness | `NULLS NOT DISTINCT` | Every root topic has a NULL parent; under the default, PostgreSQL treats each NULL as distinct and the constraint would not cover root topics at all. Requires PostgreSQL 15 or later. |
| PostgreSQL version | 18 | Current major at the time of writing; satisfies the 15+ requirement above. Pinned in Compose and CI. |
| Constraint naming | Convention on `Base.metadata` | Deterministic names, so a downgrade can drop a constraint on a database it did not create. |
| `DATABASE_URL` | Required, no default | It names an external system and carries credentials. Every other setting describes how the process runs and has a safe universal value; this one has none. |

### Migrations are never applied automatically

Neither application startup nor a container entrypoint runs `alembic upgrade`. This follows
[ADR-005](ADR-005-docker-compose-local-development.md) and `database/migrations.md`: applying a
migration stays an explicit, reviewable action.

## Consequences

### Positive

- Test fixtures, repositories, and the Alembic environment share one execution model, so no code
  path needs an async and a sync variant.
- Constraints documented in `schema.md` are enforced by the database rather than by convention, and
  each is covered by a test that attempts the write it forbids.
- The schema grows with the code that reads it, so no table's shape is fixed before its requirements
  are.
- A misconfigured or absent `DATABASE_URL` fails at startup naming the field, rather than at the
  first query.

### Negative

- Moving to asynchronous persistence later means changing every repository signature and its
  callers. Repository ports would absorb some of it, but not the call sites.
- Synchronous database calls occupy threadpool workers. At a scale this MVP does not target, that
  becomes a throughput ceiling.
- `DATABASE_URL` having no default means `python -m app.main` no longer starts from a clean
  checkout without configuration, and importing `app.main` now requires the variable to be set.
- Validated text accepts a value the application forgot to constrain until the `CHECK` rejects it at
  write time, where a PostgreSQL enum would fail earlier for some tooling.

### Neutral

- Curriculum tables exist with no repository, use case, or endpoint reading them. That arrives with
  the curriculum seed and API in the remainder of Milestone 1.

## Alternatives considered

### Asynchronous SQLAlchemy with psycopg 3 or asyncpg

Matches FastAPI's asynchronous routes end to end and avoids threadpool hops.

**Not selected:** it buys throughput this milestone cannot use, while adding async test fixtures, an
async Alembic environment, and a second way for a contributor to get a session wrong. psycopg 3
serves both models, so adopting async later is a change of engine construction and repository
signatures rather than a change of driver.

### Create the entire documented schema in one migration

Every table in `schema.md` is approved, so creating all of them is defensible and avoids a migration
per milestone.

**Not selected:** it would force decisions that no current requirement constrains — the
`day_of_week` numbering convention, the default learner timezone, numeric precision for scores and
marks — and `schema.md` flags each as undecided. Deciding them from an implementation seat is
exactly what `00-project-context.md` prohibits.

### PostgreSQL enum types for controlled values

Stronger typing and a smaller stored representation.

**Not selected:** every added value becomes an `ALTER TYPE` migration, and enum changes interact
awkwardly with transactional DDL. The `CHECK` form expresses the same constraint with cheaper
evolution, which matters while the vocabulary is still settling.

### Leave the single-active-version rule to application code

Fewer database objects, and the rule stays visible in the use case that enforces it.

**Not selected:** seed tooling and manual correction both write outside any use case, and this is
precisely the "durable invariant" that `coding-standards.md` says to express as a database
constraint where practical.

## Implementation notes

- Models and engine construction live in `backend/app/infrastructure/persistence/`; only the
  composition root builds them, and no domain or application module imports SQLAlchemy.
- The Alembic environment is `backend/migrations/env.py`, configured by `backend/alembic.ini`.
  Revision identifiers use the dated `YYYYMMDD_NN` form required by `database/migrations.md`.
- `backend/tests/integration/` applies the migration to a real database, compares the models against
  the resulting schema, exercises each constraint, and runs the downgrade. It reads
  `TEST_DATABASE_URL` and skips when that is unset, so it never touches development data.
- The CI `database` job supplies an ephemeral PostgreSQL service for those tests.
- Remaining open items for the project owner, none of which this record decides: the `day_of_week`
  numbering convention, the default learner timezone, and numeric precision for score columns. Each
  is needed by the milestone that introduces the table using it.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-003: Use PostgreSQL for structured persistence](ADR-003-postgresql-persistence.md) — the decision this record implements
- [ADR-005: Use Docker Compose for local development](ADR-005-docker-compose-local-development.md) — why migrations stay an explicit step
- [ADR-009: Name and validate configuration variables explicitly](ADR-009-configuration-naming-and-validation.md) — the category `DATABASE_URL` belongs to
- [Database schema](../database/schema.md)
- [Database migrations](../database/migrations.md)
- [Environments and configuration](../deployment/environments.md)
- [CI/CD strategy](../deployment/ci-cd.md) — the `database` job that verifies this migration
- [Architecture decision register](../architecture/decisions.md) — DEC-024

