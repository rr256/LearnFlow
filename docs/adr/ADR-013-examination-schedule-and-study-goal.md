---
title: "ADR-013: Model an Examination Period as a Published Window of Reference Data"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-06
related:
  - ../00-project-context.md
  - ADR-003-postgresql-persistence.md
  - ADR-009-configuration-naming-and-validation.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-012-curriculum-seed-and-reconciliation.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-016-learner-onboarding-api-contracts.md
  - ADR-018-weekly-availability-slots.md
  - ADR-019-study-goal-planning-preferences.md
  - ../database/schema.md
  - ../database/migrations.md
  - ../domain/domain-model.md
  - ../domain/entities.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../api/endpoints.md
  - ../deployment/environments.md
  - ../architecture/decisions.md
---

# ADR-013: Model an Examination Period as a Published Window of Reference Data

## Status

Accepted — 2026-08-01

## Implementation status

*Note added 2026-08-01, later the same day. The decision below is unchanged, and in particular the
deferral it records still stands.*

**The learner and study-goal endpoints remain deferred.** LRN-001, LRN-002, and GOAL-001 to GOAL-005
are still unimplemented, for exactly the reason recorded under *Reconciliation is an application use
case, and there is no HTTP surface yet*: their request and response schemas are written when the
client that consumes them exists, so a public contract is not fixed ahead of its first caller. The
examination schedule and the study goal are still written and read only by
`scripts.seed_examination_schedule` and `scripts.set_study_goal`. No examination-schedule endpoint
exists either; an examination window reaches a client through a goal response, and there is no goal
response yet.

**What has changed is elsewhere.** The curriculum read endpoints CUR-001 to CUR-003 are implemented.
Two consequences for this record, neither altering its decision:

- **One statement here is now stale.** Under [Alternatives considered](#add-the-study-goal-endpoints-in-this-change),
  the reason for not adding the goal endpoints cites `schema.md` as recording "the curriculum area's
  first-API-contract review as pending for the same reason". That review has since been discharged —
  the curriculum area is fully reviewed, and it required no schema change. The *argument* is
  unaffected: the curriculum endpoints could be written because their client-facing shape follows
  from curated reference data, whereas a study goal's does not. Only the supporting example has
  moved on.
- **The response contract these endpoints will use is now fixed.** [ADR-014](ADR-014-api-response-contract.md)
  decides the envelope, the collection pagination shape, and the error-code catalogue, so when the
  goal endpoints are finally shaped, only their fields are open — not how a response or a failure is
  wrapped. That narrows what the deferred decision still has to settle.

The learner-planning area's own first-API-contract review in
[database/schema.md](../database/schema.md) stays **pending**, as it must while these endpoints do
not exist.

### Implementation status — 2026-08-03

**A frontend client now exists.** A Next.js application serves a read-only curriculum view over
CUR-001 to CUR-003, per [ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md).

That matters here because of what this record's deferral rests on: the endpoints wait until "the
frontend that consumes them exists", so a public contract is not fixed ahead of its first caller.
A frontend application now exists; a screen that would consume these endpoints does not.

**The deferral is therefore due for re-evaluation, and it is the next decision in this area** rather
than a position that continues by default. Two things should be weighed when it is taken, neither
settled here:

- The client that exists is read-only and consumes curriculum reference data only. It has no learner
  setup, no goal screen, and no authentication, so it is not yet a caller whose needs would shape
  LRN-001, LRN-002, or GOAL-001 to GOAL-005. Whether the deferral's condition means an application
  exists or a *screen for these endpoints* exists is precisely what has to be settled.
- What a caller would fix is now narrower than when this record was accepted.
  [ADR-014](ADR-014-api-response-contract.md) already decides the envelope, the collection pagination
  shape, and the error catalogue, so only the fields remain open.

**One further statement above is now overtaken.** The Neutral consequence "`examination_schedules`
and `study_goals` are written but read by nothing but the commands that write them. The API arrives
with the frontend in Milestone 2" assumed the two would arrive together. The frontend has arrived
without them, which is the situation this note exists to record. The first sentence of that bullet
still holds. As with the 2026-08-01 note, the accepted text is left as written.

**Nothing about the deferral changed in the change that added the frontend.** No learner or
study-goal endpoint was added, no schema for one was written, and the examination schedule and study
goal are still reached only by `scripts.seed_examination_schedule` and `scripts.set_study_goal`. The
learner-planning area's first-API-contract review in [database/schema.md](../database/schema.md)
accordingly stays **pending**.

### Implementation status — 2026-08-05

**The deferral is discharged, for six of the seven endpoints.** A learner setup screen now exists and
consumes them, which settles the ambiguity the note above identified under either reading of the
condition. [ADR-016](ADR-016-learner-onboarding-api-contracts.md) fixes the request and response
contracts of LRN-001, LRN-002, and GOAL-001 to GOAL-004, and adds EXM-001 so a learner can choose a
published cycle rather than name one — the gap this record left when it said an examination window
reaches a client through a goal response, which a learner without a goal has not got.

**GOAL-005 remains deferred, but for a different reason than this record gave.** It waits on
`availability_slots` and the `day_of_week` numbering convention that
[ADR-011](ADR-011-sqlalchemy-persistence-implementation.md) keeps open — a schema decision, which a
caller's existence does not unblock. The bullet under *Neutral* below already anticipated this:
`availability_slots` "stays behind, because it would force the `day_of_week` convention that no
requirement yet constrains."

**Two statements above are now overtaken**, and as with the earlier notes the accepted text is left
as written:

- Under [Reconciliation is an application use case, and there is no HTTP surface yet](#reconciliation-is-an-application-use-case-and-there-is-no-http-surface-yet),
  "No endpoint is added" and the schema deferral that follows it describe the state at acceptance.
  Endpoints now exist.
- The *Neutral* bullet "`examination_schedules` and `study_goals` are written but read by nothing but
  the commands that write them" no longer holds: EXM-001 and the goal endpoints read both.

**Nothing else changed.** The window model, the provenance rules, the `CHECK` requiring a goal to aim
at something, and the default learner timezone are all implemented as decided here, and ADR-016
required **no migration** — the tables this record created hold everything the new contracts return.
The learner-planning and examination-schedule first-API-contract reviews in
[database/schema.md](../database/schema.md) are accordingly discharged.

### Implementation status — 2026-08-06

**GOAL-005 is implemented, and the deferral this record began is discharged in full.**
`availability_slots` now exists, created by migration `20260806_01`, and
[ADR-018](ADR-018-weekly-availability-slots.md) fixes the contract that replaces a goal's weekly
availability. The `day_of_week` convention that held it back was **retired rather than chosen**: the
column stores the day's `snake_case` name, so no numbering exists for a reader or a client to get
wrong.

**One statement under *Neutral* is now overtaken**, and as with the earlier notes the accepted text is
left as written: "`availability_slots` stays behind, because it would force the `day_of_week`
convention that no requirement yet constrains." It no longer stays behind, and the convention it would
have forced no longer exists. The bullet's reasoning was correct while it applied — the table was
created in the change whose requirement finally constrained its shape, which is exactly what holding
it back was for.

**Two things this record left open remain open.** `study_goals.planning_preferences` is still not
created, for the reason given in the same *Neutral* bullet: nothing reads it and its shape is
undecided. GOAL-004 accordingly still does not accept it, so FR-002's "available study time and basic
planning preferences" criterion is now **partly** met rather than unmet. How superseded examination
periods are retired, and whether a learner may hold goals for more than one program at a time, are
untouched.

**Nothing else changed.** The window model, the provenance rules, and the goal `CHECK` are unaffected;
ADR-018's migration creates one empty table and alters none of the four this record created.

### Implementation status — 2026-08-06, later the same day

**`study_goals.planning_preferences` now exists, so the last thing this record left open in the
learner-planning area is taken.** [ADR-019](ADR-019-study-goal-planning-preferences.md) fixes the
contract GOAL-001 and GOAL-004 accept it under, and migration `20260806_02` adds it — as **two typed
columns rather than one `jsonb` payload**, because no `CHECK` can guard a key inside JSON and
`topic_sequencing` is a controlled value.

**One statement under *Neutral* is now overtaken**, and as with the earlier notes the accepted text is
left as written: "`study_goals.planning_preferences` is not created, for the same reason: nothing reads
it, and its shape is undecided." Nothing reads it still — no plan is generated — so the first half of
that reason holds and ADR-019 records it as a deliberate departure from ADR-011's ordering rule rather
than a refutation of it. The second half no longer applies: the shape is decided.

**FR-002's second acceptance criterion is now met in full**, where the note above reported it as partly
met. [endpoints.md](../api/endpoints.md#fr-002-acceptance-criteria) carries the count.

**Nothing else changed.** The window model, the provenance rules, the goal `CHECK`, and the default
learner timezone are unaffected, and the migration alters no column this record created. The two other
things this record left open — how superseded examination periods are retired, and whether a learner may
hold goals for more than one program at a time — are untouched.

## Context

[FR-002](../requirements/functional.md) requires a learner to set a target
examination date before planning begins, and
[database/schema.md](../database/schema.md) approved `study_goals.target_date` as
a single `date` to hold it.

Implementing that against a real examination showed the column cannot hold what
the source actually publishes. IIT Madras publishes GATE 2027 as a set of sitting
days — 6–7, 13–14, and 20–21 February 2027 — and does not say which of them the
Computer Science paper falls on. It also states that every date it publishes is
liable to change. A single `target_date` therefore has no honest value to hold:
any date inside the window is a guess, and a guess stored in a `date` column
becomes a deadline the whole planner treats as fact.

Four questions could not be avoided once that was clear, and none had an approved
answer:

1. **Where an examination calendar lives.** It describes the world, not the
   learner, and every learner aiming at the same cycle must see the same dates.
2. **How a period that is not one day is stored**, given that registration,
   examination, and results are all ranges of different shapes.
3. **How "liable to change" survives into the database**, rather than being lost
   between the source and the row.
4. **What a study goal aims at** once a single target date is no longer always
   available.

A fifth question arrives with the same change: creating `learners` forces the
**default learner timezone**, which
[ADR-011](ADR-011-sqlalchemy-persistence-implementation.md) records as an open
item for the project owner.

## Decision

### An examination schedule is reference data, seeded with its provenance

Two tables, in a new *Examination schedule* schema area:
`examination_schedules` holds one published calendar per learning program and
cycle — `gate-cse` and `2027` — with its organising body, source URL, the date
the source was read, and its confirmation status. `examination_periods` holds its
dated periods.

This follows [ADR-012](ADR-012-curriculum-seed-and-reconciliation.md): like the
curriculum, a schedule is curated data with a traceable source, loaded by an
idempotent seed rather than typed in by a learner. `source_reference` is `NOT
NULL`, unlike the curriculum's, because a stored date with no traceable origin
cannot be checked when the examining body revises it.

### The examination is stored as dated periods, never as one date

A period carries `period_type`, `starts_on`, and `ends_on`. GATE 2027's three
sitting weekends are three `examination` periods, not one 6–21 February range:
eleven of the days in that range hold no examination, and a window spanning them
would misstate what was published. A period whose start and end are the same day
is a single-day event, which is how the results announcement is stored.

The examination window a plan is built against is derived — first sitting day to
last — from the `examination` periods alone. Registration and results periods
bracket the examination rather than being it, and including them would widen the
window by months. The derivation lives in the use case, not the repository or a
stored column.

`period_type` covers `registration`, `late_registration`, `examination`, and
`results`. All four are persisted: the registration deadlines are the nearest
actionable dates a learner has, and documenting them while storing only the
examination would leave the product unable to surface them.

### `schedule_status` carries "liable to change" into the database

A schedule is `provisional` until the examining body confirms its dates, and
`confirmed` afterwards. The bundled GATE 2027 schedule is `provisional`, because
its source says so. Every report that prints the dates prints the qualification
with them.

### A study goal aims at an examination cycle, a target date, or both

`study_goals.target_date` becomes nullable and gains a nullable
`examination_schedule_id`, with a `CHECK` requiring at least one of them. A
learner preparing for a published examination need not invent a date; a learner
following no examination need not invent a cycle; a goal with neither has no
horizon to plan against and is refused.

The goal stores a **reference** to the schedule, never a copy of its dates, so a
re-seeded correction reaches every goal at once and no goal can drift from the
published source.

### The default learner timezone is `APP_DEFAULT_TIMEZONE`, defaulting to `Asia/Kolkata`

Core runtime under [ADR-009](ADR-009-configuration-naming-and-validation.md): it
describes how this installation runs, selects no adapter, and names no vendor. It
is validated at startup as a real IANA zone through the standard library's
`zoneinfo`, which needs no new dependency — `tzdata` already ships as a
dependency of psycopg.

This settles one of the three open items ADR-011 left to the project owner. The
`day_of_week` numbering convention and numeric precision for score columns remain
open; the tables that need them are not created here.

### Reconciliation is an application use case, and there is no HTTP surface yet

The matching rules live in
`backend/app/application/use_cases/seed_examination_schedule.py` and
`set_study_goal.py`, behind repository ports. Two composition-root commands —
`scripts/seed_examination_schedule.py` and `scripts/set_study_goal.py` — read
configuration and open a database.

No endpoint is added. [endpoints.md](../api/endpoints.md) defines GOAL-001 to
GOAL-005 and LRN-001 at intent level; their request and response schemas are
written when the frontend that consumes them exists, so a contract is not fixed
ahead of its first caller.

## Consequences

### Positive

- The product can state what is actually known — an examination window, from a
  named source, read on a known date, still liable to change — instead of a date
  nobody published.
- A revised schedule is a data-file edit and a re-seed; every goal pointing at it
  follows, with no learner-record migration.
- Another learning program's calendar is a new data file, not a code change, and
  a program whose examination is one day stores one period.
- The registration deadlines are queryable, so the product can surface the
  nearest action rather than only the distant one.
- A goal cannot exist without a horizon, enforced by the database rather than by
  convention.

### Negative

- Deriving the window on every read costs a query for the periods. At six rows
  per cycle this does not matter; a stored window would be faster and would drift.
- A period whose sitting day moves reads as a new period alongside the old one,
  because the natural key includes the start date. Nothing is deleted, so a
  schedule revised repeatedly accumulates superseded rows. Retiring them needs a
  separate, deliberate mechanism that does not exist yet — the same gap ADR-012
  records for curriculum.
- Two constraint names on `examination_periods` are shortened by hand, because
  the naming convention would generate 68-character identifiers that PostgreSQL
  truncates at 63. They are the first constraints in the repository that do not
  read exactly as the convention would spell them.
- `study_goals.target_date` is now nullable, so every future reader must handle
  its absence rather than relying on the column.

### Neutral

- `examination_schedules` and `study_goals` are written but read by nothing but
  the commands that write them. The API arrives with the frontend in Milestone 2.
- This brings `learners` and `study_goals` forward from Milestone 2 into
  Milestone 1. `availability_slots` stays behind, because it would force the
  `day_of_week` convention that no requirement yet constrains.
- `study_goals.planning_preferences` is not created, for the same reason: nothing
  reads it, and its shape is undecided.

## Alternatives considered

### Keep `target_date` as a single non-null date

The approved shape, and the simplest for a planner to consume.

**Not selected:** there is no date to put in it. The learner would either pick a
day inside a window they cannot yet know, or the system would default to the
window's first day — recording a guess as a deadline, which is precisely what the
window model exists to prevent.

### Store the window as two columns on `study_goals`

`target_period_start` and `target_period_end`, with a source reference and a
provisional flag alongside them.

**Not selected:** it makes every learner keep a private copy of published data.
Two learners aiming at the same examination could hold different dates, a
correction would have to be applied goal by goal, and the provenance would be
duplicated per row rather than held once where it can be checked.

### One reference table with explicit date columns

`registration_opens_on`, `examination_starts_on`, `examination_ends_on`, and so
on: one row per cycle, no child table.

**Not selected:** a single examination start and end cannot express three
separate weekends without claiming the eleven days between them, and each
additional kind of date the institute publishes would be a schema migration
rather than a data edit.

### Extend the curriculum seed file and use case

One data file, one command, one provenance block for a program-year.

**Not selected:** it widens a file format governed by an accepted ADR, and it
couples two things that change on different cadences. A syllabus is stable for a
year; a provisional schedule is expected to be corrected. Retiring a syllabus
version would also drag the schedule with it.

### Add the study-goal endpoints in this change

The learner could set a goal over HTTP immediately.

**Not selected:** it fixes public request and response contracts before any
client exists to validate them against, and `schema.md` already records the
curriculum area's first-API-contract review as pending for the same reason.

## Implementation notes

- Migration `20260801_01_create_examination_schedule_and_learner_goal_tables`
  creates all four tables. It is additive and creates them empty.
- `backend/scripts/gate_cse_examination_schedule.json` holds the GATE 2027 dates.
  Its `$comment` block records the source, the transcription rules, and the one
  inference the file makes: the source publishes a late-registration *closing*
  date rather than an opening one, so the period is recorded as beginning the day
  after regular registration closes.
- The dates were supplied by the project owner from
  <https://gate2027.iitm.ac.in/> and transcribed as given. They were not
  independently fetched during implementation, which `source_checked_on` recorded
  as 2026-07-31 at the time. The project owner verified them against the official
  IIT Madras source on 2026-08-01, and `source_checked_on` now records that date.
- Local setup order is migrations, then `seed_curriculum`, then
  `seed_examination_schedule`, then `set_study_goal`. Each step refuses to run
  ahead of its predecessor with a message naming the command to run first.
- Open for a later decision, and deliberately not settled here: how superseded
  examination periods are retired, whether a study goal may exist for more than
  one learning program at a time, and the request/response schemas for GOAL-001
  to GOAL-005.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-003: Use PostgreSQL for structured persistence](ADR-003-postgresql-persistence.md)
- [ADR-009: Name and validate configuration variables explicitly](ADR-009-configuration-naming-and-validation.md) — the category `APP_DEFAULT_TIMEZONE` belongs to
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](ADR-011-sqlalchemy-persistence-implementation.md) — the per-milestone ordering this change follows, and the open item it settles
- [ADR-012: Load curriculum as reconciled reference data from a versioned file](ADR-012-curriculum-seed-and-reconciliation.md) — the seed rules this record reuses
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the envelope and error contract the deferred goal endpoints will answer in
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the client whose existence reopens the deferral above
- [ADR-016: Fix the learner setup API contracts](ADR-016-learner-onboarding-api-contracts.md) — the record that discharges that deferral, and the endpoint schemas this one left open
- [ADR-018: Store weekly availability as named days replaced a week at a time](ADR-018-weekly-availability-slots.md) — the record that creates the `availability_slots` table this one held back, and discharges the last of the deferral
- [ADR-019: Store planning preferences as typed columns replaced as a group](ADR-019-study-goal-planning-preferences.md) — the record that creates the `planning_preferences` columns this one held back, and why they are typed rather than `jsonb`
- [Database schema](../database/schema.md) — the tables and constraints this record decides
- [Database migrations](../database/migrations.md) — the seed's commands and operational rules
- [Domain model](../domain/domain-model.md) — the examination schedule concept
- [Domain entities](../domain/entities.md)
- [Terminology](../domain/terminology.md) — the canonical terms this record introduces
- [Functional requirements](../requirements/functional.md) — FR-002, the requirement this record reinterprets
- [API endpoints](../api/endpoints.md) — GOAL-001 to GOAL-005 and LRN-001, deferred by this record
- [Environments and configuration](../deployment/environments.md) — the `APP_DEFAULT_TIMEZONE` catalogue entry
- [Architecture decision register](../architecture/decisions.md) — DEC-026
