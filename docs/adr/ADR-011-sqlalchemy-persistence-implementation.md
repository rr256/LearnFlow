---
title: "ADR-011: Implement PostgreSQL Persistence Synchronously and Migrate Per Milestone"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-13
related:
  - ADR-020-initial-study-plan-generation.md
  - ../00-project-context.md
  - ADR-003-postgresql-persistence.md
  - ADR-005-docker-compose-local-development.md
  - ADR-009-configuration-naming-and-validation.md
  - ADR-012-curriculum-seed-and-reconciliation.md
  - ADR-013-examination-schedule-and-study-goal.md
  - ADR-014-api-response-contract.md
  - ADR-018-weekly-availability-slots.md
  - ADR-019-study-goal-planning-preferences.md
  - ADR-021-plan-item-completion.md
  - ADR-024-plan-item-skipping.md
  - ADR-025-learner-postponement.md
  - ../database/schema.md
  - ../database/migrations.md
  - ../api/endpoints.md
  - ../deployment/environments.md
  - ../deployment/ci-cd.md
  - ../architecture/decisions.md
  - ADR-021-plan-item-completion.md
---

# ADR-011: Implement PostgreSQL Persistence Synchronously and Migrate Per Milestone

## Status

Accepted — 2026-07-31

## Implementation status

*Note added 2026-07-31. The decision below is unchanged; this records what has since been built
against it.*

The curriculum tables are now read and written through the persistence layer. The approved GATE CSE
curriculum seed — [ADR-012](ADR-012-curriculum-seed-and-reconciliation.md) — loads them through a
`CurriculumSeedRepository` port, a SQLAlchemy adapter implementing it, and an application use case
that owns the reconcile rules.

This supersedes the *Neutral* consequence recorded below, which noted that the curriculum tables
existed with nothing reading them and that this would arrive "with the curriculum seed and API in the
remainder of Milestone 1". The seed half has arrived; the API half has not. No HTTP endpoint reads
the curriculum tables yet.

Two further points of fact, neither altering the decision:

- The synchronous execution model chosen here is now exercised by real repository code rather than by
  models alone. `sqlalchemy.orm.Session` carries the seed's whole run as one unit of work, and
  nothing has required an asynchronous variant.
- The curriculum area now spans two migrations, not one. `20260731_01_create_curriculum_tables`
  created it; `20260731_02_add_topic_code_unique_constraint` added `uq_topics_subject_id_code` after
  the seed showed that a natural key it matched on was unenforced. The "one schema area per
  milestone" ordering decision is unaffected — a follow-up migration amending an area is the
  mechanism this record prescribes, not an exception to it.

The database-enforced single-active-version rule decided below is now also checked by the seed before
it writes, so a rival active version is refused with a message naming both rather than surfacing as an
integrity error. The partial unique index remains the authority; the application check only improves
the diagnostic.

*Note added 2026-08-01. The decision below is unchanged; this closes one of the open items it left.*

**The default learner timezone is implemented.** It is `APP_DEFAULT_TIMEZONE`, a core-runtime
configuration variable defaulting to `Asia/Kolkata`, validated at startup against the standard
library's zone database. The composition root supplies it when a learner record is created;
`learners.timezone` carries no database default, so no row can acquire a zone nobody chose. No
dependency was added — `tzdata` already ships as a dependency of psycopg.

This supersedes the first entry in the *Remaining open items for the project owner* list under
[Implementation notes](#implementation-notes) below. The other two are untouched and remain open: the
`day_of_week` numbering convention, needed by `availability_slots`, and numeric precision for score
columns. Both belong to tables that do not exist yet.

The rationale is recorded in [ADR-013](ADR-013-examination-schedule-and-study-goal.md), the change
that created `learners` and therefore had to settle it, and the variable is catalogued in
[environments and configuration](../deployment/environments.md#application).

Migration `20260801_01_create_examination_schedule_and_learner_goal_tables` also brought `learners`
and `study_goals` forward from Milestone 2 into Milestone 1, and added a seventh schema area for
examination schedules. The "one schema area per milestone" ordering decision is unaffected: the
milestone that first needed those tables created them, which is what this record prescribes.

*Note added 2026-08-01, later the same day. The decision below is unchanged; this records the
arrival of the API half and supersedes the two statements naming it as still to come.*

**HTTP endpoints now read the curriculum tables.** CUR-001 to CUR-003 serve the learning programs,
one program with its active curriculum version, and a curriculum version's subjects, topics,
subtopics, and topic relationships. This supersedes both the sentence above — "The seed half has
arrived; the API half has not. No HTTP endpoint reads the curriculum tables yet" — and the *Neutral*
consequence recorded under [Consequences](#neutral), which said the curriculum tables existed with
nothing reading them. Neither statement is true any longer, and the *Neutral* consequence is now
discharged in full.

Three points of fact, none altering the decision:

- The synchronous execution model chosen here now serves HTTP requests, not only the seed. A
  `sqlalchemy.orm.Session` is opened per request by the composition root and closed when the response
  has been produced. FastAPI runs the synchronous route in its worker threadpool exactly as this
  record anticipated, and nothing has required an asynchronous variant.
- Reads go through a second, read-only port, `CurriculumRepository`, rather than through the seed
  port. `expire_on_commit=False` on the session factory continues to matter for the reason recorded
  when it was chosen: a record stays readable while it is mapped to a response.
- **No schema change resulted.** The API-contract review that `database/schema.md` held open for the
  curriculum area is now discharged, and it found that every column an endpoint returns already
  exists. The curriculum area is fully reviewed.

The two remaining open items are untouched and stay open: the `day_of_week` numbering convention,
needed by `availability_slots`, and numeric precision for score columns. Both belong to tables that
do not exist yet.

The response contract those endpoints answer in is recorded in
[ADR-014](ADR-014-api-response-contract.md).

*Note added 2026-08-06. The decision below is unchanged; this closes the second of the three open
items it left.*

**The `day_of_week` numbering convention is retired, not chosen.** `availability_slots` now exists,
created by migration `20260806_01`, and its `day_of_week` is `varchar(16)` holding `monday` to
`sunday` rather than the `smallint` `database/schema.md` described. There is therefore no numbering
convention to document: the open item is closed by removing the question rather than by answering it.
The rationale is in [ADR-018](ADR-018-weekly-availability-slots.md), and
[schema.md](../database/schema.md#availability_slots) records the changed column type against the
table.

Three points of fact, none altering the decision:

- **This is the validated-text rule below, applied again.** *Controlled values are validated text, not
  PostgreSQL enums* covers `day_of_week` exactly as it covers `curriculum_versions.status`. A
  `smallint` would have made it the only numeric enumerated value in the schema.
- **The per-milestone ordering worked as this record intended.** `availability_slots` was held back
  through three migrations precisely because creating it would have fixed a convention no requirement
  constrained — the case *Create the entire documented schema in one migration* names by name — and it
  was created in the change whose requirement finally arrived.
- The learner-planning area is one migration from complete. `study_plans` and `plan_items` remain, and
  both arrive with Milestone 3's planning code.

**One open item is left**: numeric precision for score columns, which belongs to tables that do not
exist. This supersedes, in part, the *Remaining open items* bullet under
[Implementation notes](#implementation-notes) and the same statement in the two notes above. As
elsewhere in this repository, the accepted text is left as written.

*Note added 2026-08-06, later the same day. The decision below is unchanged, and this records a
deliberate exception to one part of it rather than an amendment.*

**`study_goals` gained two planning-preference columns before any code reads them**, which is a
departure from the per-milestone ordering rule this record sets out under
[the first migration creates the curriculum area only](#the-first-migration-creates-the-curriculum-area-only).
[ADR-019](ADR-019-study-goal-planning-preferences.md) takes that decision and records both sides of it:
no planner exists, so the risk this record names is real, but
[FR-002](../requirements/functional.md#fr-002-initial-learner-setup)'s criterion asks what a learner can
*set*, and availability was counted on the same basis one change earlier.

**The rule itself is not weakened.** It still governs `study_plans`, `plan_items`,
`study_activities`, `revision_records`, and every resource and assessment table, none of which exists.
ADR-019 is the second recorded exception to it, after `learner_topic_progress.stage_source` under
[ADR-017](ADR-017-topic-progress-api-and-schema.md); each is argued individually rather than by
precedent.

**Two things did not change.** The validated-text rule was followed rather than departed from —
`topic_sequencing` is `varchar(32)` guarded by a `CHECK`, not a key inside a `jsonb` payload, which is
the same reasoning applied to `day_of_week`. And **the one open item is still the one open item**:
numeric precision for score columns, in tables that do not exist. The learner-planning area remains one
migration from complete, since this change adds columns to an existing table rather than a table.

*Note added 2026-08-06, later the same day. The decision below is unchanged; this records the
completion of one schema area and narrows where the ordering rule still applies.*

**The learner-planning area is complete.** Migration `20260806_03` creates `study_plans` and
`plan_items`, the two tables this record's notes above described as "one migration from complete", and
they arrive **with** the planning code that reads them — which is the ordering rule below applied
rather than departed from. [ADR-020](ADR-020-initial-study-plan-generation.md) records the decision.

**Three statements above are overtaken**: "The learner-planning area is one migration from complete";
"[the ordering rule] still governs `study_plans`, `plan_items`, `study_activities`,
`revision_records`, and every resource and assessment table, none of which exists"; and "The
learner-planning area remains one migration from complete." The rule now governs `study_activities`,
`revision_records`, and every resource and assessment table.

Two further points of fact, neither altering the decision:

- **The validated-text rule was applied a fourth time.** `plan_type`, `study_plans.status`,
  `plan_items.action_type`, and `plan_items.status` are `varchar(32)` guarded by a `CHECK` rather than
  the bare `text` [schema.md](../database/schema.md#study_plans) documented, following `day_of_week`
  and `topic_sequencing`.
- **`plan_items.status` is a third recorded exception to the ordering rule**, after
  `learner_topic_progress.stage_source` under ADR-017 and the planning preferences under ADR-019. It
  is created although nothing writes anything but `planned`, for the reason ADR-017 gave: a state
  added after learners hold plans could only be backfilled by guessing.

**The one open item is still the one open item**: numeric precision for score columns, in tables that
do not exist.

*Note added 2026-08-08. The decision below is unchanged; this records the discharge of the third
ordering-rule exception the note above created.*

**The third exception is discharged, and it cost no migration.** PLN-004 now writes
`plan_items.status` and `plan_items.completed_at`, moving an item between `planned` and `completed`.
Both columns, the `status` `CHECK`, and `ix_plan_items_study_plan_id_scheduled_for_status` were
created by `20260806_03`; the endpoint stored what they anticipated and **altered nothing**.
[ADR-021](ADR-021-plan-item-completion.md) records the decision.

**One statement above is overtaken**: "`plan_items.status` … is created although nothing writes
anything but `planned`." It is still the record of why the column arrived before its code, and that
argument now has its result — the columns were the right shape when the code came, so no row had to be
backfilled by guessing. Of the three recorded exceptions, this is the first to be closed;
`learner_topic_progress.stage_source` and the planning preferences each remain as their notes describe.

Two points of fact, neither altering the decision:

- **The `CHECK` is deliberately wider than the endpoint.** `skipped` and `postponed` pass it and
  PLN-004 refuses them. That is the validated-text rule working as intended: the constraint says what
  a plan item may *be*, and which of those a learner may currently *ask for* is a contract rule.
- **No constraint ties `status` to `completed_at`.** The pairing is an application rule, as
  [schema.md](../database/schema.md#plan_items-status-review-2026-08-08) records; nothing else in this
  schema constrains one column by another.

**The one open item is still the one open item**: numeric precision for score columns, in tables that
do not exist.

## Implementation status — 2026-08-13

*Note added 2026-08-13. The accepted decision below is unchanged, and so is the 2026-08-08 note's
reasoning; this records the one statement of fact in that note which the product has since
overtaken.*

**The `CHECK` on `plan_items.status` and the endpoint now admit the same four values.** The
2026-08-08 note recorded, under "Two points of fact", that "`skipped` and `postponed` pass it and
PLN-004 refuses them". Neither half is true any longer:

- **`skipped` became askable** with [ADR-024](ADR-024-plan-item-skipping.md).
- **`postponed` became askable** with [ADR-025](ADR-025-learner-postponement.md).

**The rule that note stated is unaffected, and is why nothing had to change here.** Its point was
that "the constraint says what a plan item may *be*, and which of those a learner may currently *ask
for* is a contract rule" — the two remain separate rules, and they happen to agree today. That they
agree is a fact about the product having run out of statuses only adaptation writes, not a merging of
the two. A fifth value added to the column would arrive unwritable until somebody decided it should
be askable, exactly as this record's validated-text rule intends.

**No migration, no constraint change, and no schema change followed from either.** The `CHECK`
created by `20260806_03` has carried all four values from the start, which is the same
columns-ahead-of-their-code argument the 2026-08-08 note recorded as discharged. `completed_at` is
still paired to `status` by an application rule and by no constraint, and it is still cleared by
every move off `completed` — now including a move to `postponed`.

The [schema document](../database/schema.md#plan_items-postponement-review-2026-08-11) carries the
dated review for the second writer of `postponed`, and stays authoritative for the table.

**The one open item is still the one open item**: numeric precision for score columns, in tables that
do not exist.

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
- [ADR-012: Load curriculum as reconciled reference data from a versioned file](ADR-012-curriculum-seed-and-reconciliation.md) — the first code to read and write the tables this record created
- [ADR-013: Model an examination period as a published window of reference data](ADR-013-examination-schedule-and-study-goal.md) — settles the default learner timezone this record left open
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the contract the first endpoints reading these tables answer in
- [ADR-018: Store weekly availability as named days replaced a week at a time](ADR-018-weekly-availability-slots.md) — retires the `day_of_week` convention this record left open
- [ADR-019: Store planning preferences as typed columns replaced as a group](ADR-019-study-goal-planning-preferences.md) — the recorded exception to the per-milestone ordering rule above, and the validated-text rule applied again
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](ADR-020-initial-study-plan-generation.md) — the change that completes the learner-planning area, following the ordering rule rather than departing from it
- [API endpoints](../api/endpoints.md) — CUR-001 to CUR-003, the first endpoints to read these tables
- [Database schema](../database/schema.md)
- [Database migrations](../database/migrations.md)
- [Environments and configuration](../deployment/environments.md)
- [CI/CD strategy](../deployment/ci-cd.md) — the `database` job that verifies this migration
- [Architecture decision register](../architecture/decisions.md) — DEC-024

