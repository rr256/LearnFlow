---
title: "ADR-018: Store Weekly Availability as Named Days Replaced a Week at a Time"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-06
related:
  - ../00-project-context.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-013-examination-schedule-and-study-goal.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-016-learner-onboarding-api-contracts.md
  - ADR-017-topic-progress-api-and-schema.md
  - ADR-019-study-goal-planning-preferences.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../api/versioning.md
  - ../database/schema.md
  - ../database/migrations.md
  - ../domain/domain-model.md
  - ../domain/entities.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../architecture/decisions.md
---

# ADR-018: Store Weekly Availability as Named Days Replaced a Week at a Time

## Status

Accepted — 2026-08-06

This record closes the last of the three open project-owner items
[ADR-011](ADR-011-sqlalchemy-persistence-implementation.md) recorded, and discharges the deferral
[ADR-016](ADR-016-learner-onboarding-api-contracts.md) left on GOAL-005. Both remain accepted and
unchanged; each carries a dated implementation-status note pointing here.

## Implementation status — 2026-08-06, later the same day

*Note added 2026-08-06. The decision below is unchanged: GOAL-005's contract, the day-name column, and
the whole-week replace are all untouched. As elsewhere in this repository, the accepted text is left as
written.*

**The other half of FR-002's criterion is now delivered.**
[ADR-019](ADR-019-study-goal-planning-preferences.md) adds the learner's planning preferences to
`study_goals` and to GOAL-001 and GOAL-004.

**Two statements are overtaken:**

- Under [Positive](#positive), "**FR-002's second acceptance criterion is now half met**… Basic planning
  preferences remain unmet — `study_goals.planning_preferences` is not created, and ADR-013 holds its
  shape undecided." The columns now exist and the criterion is **met in full**;
  [endpoints.md](../api/endpoints.md#fr-002-acceptance-criteria) carries the count.
- Under [Implementation notes](#implementation-notes), the open item "whether `planning_preferences`
  arrives with the planner or before it" is settled: **before it**, deliberately, and ADR-019 records
  that as a departure from ADR-011's ordering rule together with the risk it carries.

**Three of this record's rules were reused rather than reinvented**, which is what it says a later
change should do: the whole-group replace is this record's whole-week replace applied to a set of
columns, an unset preference is its zero-versus-absent distinction applied to a value, and a session
length is a duration for the same reason a slot holds minutes rather than clock times. ADR-019 also
departs from a documented `schema.md` target the way this record did, and for a related reason — a
`CHECK` cannot guard what is not a column.

**Nothing else changed.** `availability_slots` is unaltered, nothing totals a week, and no plan is
generated from either input.

## Context

[FR-002](../requirements/functional.md#fr-002-initial-learner-setup) requires a learner to set
available study time before planning begins. GOAL-005 has been catalogued since the documentation
foundation and deferred ever since — first with the rest of the learner endpoints by
[ADR-013](ADR-013-examination-schedule-and-study-goal.md), then alone by ADR-016, which named the
reason precisely: it needs `availability_slots`, and creating that table would fix "the `day_of_week`
numbering convention ADR-011 records as an open project-owner decision. Choosing it as a side effect
of a form is exactly what ADR-011 exists to prevent."

That decision is now taken deliberately rather than as a side effect, and four questions had to be
answered with it. [ADR-014](ADR-014-api-response-contract.md) had already fixed the envelope, the
pagination shape, and the error catalogue, so none of those was open.

1. **What a slot is.** [schema.md](../database/schema.md#availability_slots) approves one row per
   goal and day carrying `available_minutes`. It records that a pending area's columns are "an
   approved target, not a committed shape", so clock-time ranges were available and had to be
   considered rather than assumed away.

2. **How a day of the week is stored and sent.** The approved column is `smallint` holding "0–6
   according to documented convention", and no document says which convention. Python's
   `date.weekday()` makes Monday zero; JavaScript's `Date.getDay()` and PostgreSQL's `EXTRACT(DOW)`
   both make Sunday zero. An off-by-one here misfiles a whole week with no error anywhere.

3. **How a week is written, and how it is read back.** "Add, edit, and remove a slot" can be three
   endpoints or one. GOAL-003's catalogue entry also promised an availability summary and has been
   explicitly withholding one "for the reason given under GOAL-005", so where a saved week is read
   from was equally open.

4. **What zero minutes means.** The approved constraint is `available_minutes >= 0`, which would be
   pointless if zero were refused — but a day holding zero and a day holding nothing are different
   claims, and nothing said which the product makes.

## Decision

### A slot is one day's worth of minutes, as `schema.md` approves

`availability_slots` is created with `id`, `study_goal_id`, `day_of_week`, `available_minutes`, and
the audit timestamps, keyed uniquely on `(study_goal_id, day_of_week)`. A goal therefore holds at most
seven rows, and "edit Monday" addresses a day rather than a row.

Availability belongs to the **study goal**, not to the learner, as `schema.md` has it: a learner who
archives one goal and starts another is describing a different week.

**No clock times.** A slot says how much time a day holds, not when in the day it falls. Wall-clock
columns would raise which zone reads them — `learners.timezone` exists, but nothing this feature does
needs a time of day, and a planner that places work inside a day is Milestone 3's problem. Adding
them later is an additive migration; removing them would not be.

### `day_of_week` is a `snake_case` day name, so there is no numbering convention

`varchar(16)` holding `monday` to `sunday`, guarded by a `CHECK`. **This does not answer the open
question ADR-011 recorded; it removes it.** There is no numbering left for a contributor to document,
a reader to look up, or a client to mis-map.

It is also the consistent choice. Every other controlled value in this schema is validated text
guarded by a `CHECK` rather than a number or a PostgreSQL enum
([ADR-011](ADR-011-sqlalchemy-persistence-implementation.md)) — `late_registration`,
`recommended_before`, `practice_ready` — and
[ADR-017](ADR-017-topic-progress-api-and-schema.md) fixed the rule that the stored form is the wire
form while only the *label* is presentation. A day name satisfies both; a `smallint` would have made
`day_of_week` the schema's only numeric enumerated value.

The cost is that a week cannot be ordered by an `ORDER BY`. Monday-first is presentation, so the
application sorts against a fixed list, and the repository promises no order at all.

### GOAL-005 replaces the whole week; a day it does not name is removed

`PUT /api/v1/study-goals/{goal_id}/availability`, exactly the method and path the catalogue has
carried since before it was implementable. The body is the complete week. Adding a day, editing a
day, and removing a day are therefore one request each — and an edit spanning three days is one
transaction, so it cannot leave one day saved and two lost.

An explicit empty list clears the goal's availability. `slots` is **required**, so a body that forgot
it cannot silently clear a learner's week; absence is a `422` and an empty list is a deliberate act.

A day whose minutes have not changed is left alone entirely, so saving the same week twice writes
nothing. That keeps the row's identifier and `created_at`, which a delete-and-reinsert would discard,
and it is the rule PRG-004 already applies to a stage a topic already holds: a repeated form
submission must not fail or churn rows on its second attempt.

**Per-slot `POST`, `PATCH`, and `DELETE` endpoints were rejected**, under *Alternatives* below.

### The saved week travels on the goal response

GOAL-001 to GOAL-004 gain an `availability` object. This discharges GOAL-003's original intent line,
and it means the setup screen and the home screen both show a saved week without a further request —
both already read GOAL-002.

A goal with nothing stored carries an **empty week**, not a null and not an absent key, so no client
needs a branch for a goal created before GOAL-005 existed. Adding the field is compatible under
[versioning](../api/versioning.md#compatible-changes-within-a-major-version).

**No slot identifier is exposed.** GOAL-005 addresses a week, not a row, so an identifier no client
can use would be a field the contract had to keep forever.

This is deliberately the opposite of the separation ADR-013 made when it refused to hang the
examination calendar off CUR-002, and ADR-017 made when it refused to add `learning_stage` to CUR-003.
Both of those would have made *reference data* learner-owned. A goal response is already learner-owned
and already resolves the learner, and availability belongs to the goal by foreign key — so embedding
it widens no exposure and obliges no indifferent client to carry learner data.

### Zero minutes is a day kept free; an absent day is one not set

A row carrying `0` records a rest day the learner chose. A day with no row is one they have not
thought about. This is the distinction ADR-017 drew between an explicit `not_explored` and no record
at all, and it is what makes the approved `>= 0` constraint mean something. An upper bound of 1440 is
added beside it, because a day holds 1440 minutes and a larger value is always a mistake.

### Nothing totals a week

No column, no response field, and no view reports a weekly total, and nothing derives a plan from a
week. Availability is a planning input — [terminology](../domain/terminology.md) calls it "not a
measure of commitment or ability" — and turning one into an hours figure is planning work that arrives
with [Milestone 3](../roadmap/milestones.md#milestone-3-planning-and-revision).

### The write goes through a Next.js server action, and the backend gains no CORS

One form per week, posting to a `"use server"` module which calls the API with the same server-side
`API_BASE_URL` every other view uses. The browser still issues no request to the backend, so
`API_CORS_ALLOWED_ORIGINS` stays planned rather than implemented.

This inherits [ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md), ADR-016, and
ADR-017 rather than renegotiating them, which is what ADR-015 says every later screen does. Seven
number boxes and a save button have no interaction a server round trip cannot serve, and the form
works without JavaScript.

## Consequences

### Positive

- **FR-002's second acceptance criterion is now half met**: a learner can set available study time.
  Basic planning preferences remain unmet — `study_goals.planning_preferences` is not created, and
  ADR-013 holds its shape undecided — so the criterion is reported as partly met rather than met.
  [endpoints.md](../api/endpoints.md#goal-005-put-apiv1study-goalsgoal_idavailability) carries the
  current count and stays authoritative for it.
- **ADR-011's open-item list is now empty of the two schema conventions it named.** The `day_of_week`
  convention is not answered but retired; numeric precision for score columns is the last item left,
  and it belongs to tables that do not exist.
- The learner-planning schema area is one table from complete: `study_plans` and `plan_items` are all
  that remain, and both arrive with the planner that reads them.
- No implemented contract changed incompatibly. CUR-001 to CUR-003, LRN-001, LRN-002, EXM-001,
  PRG-002, and PRG-004 are untouched, and the goal responses gained an optional-to-ignore field.
- The migration creates one empty table and alters nothing, so no learner data is reinterpreted.
- A week is one write, so unlike the profile-and-goal pair ADR-016 had to accept, there is no partial
  outcome to report.

### Negative

- One more endpoint is public contract. Changing a field or a status code on it is breaking under
  [versioning](../api/versioning.md#breaking-changes).
- **Reading a page of goals now reads each goal's week.** It is one query for the whole page rather
  than one per goal, but it is a second query beside the examination periods ADR-016 already reads per
  goal.
- A week cannot be ordered in SQL, so every reader that wants Monday first depends on the application
  sorting it. A future report written in SQL alone would need a `CASE`.
- `PUT` replace means a client must send the whole week to change one day. That is the right shape for
  a form and the wrong one for an inline per-day control, which no screen has.
- **A learner cannot record two sittings on one day** — "Monday 06:00–08:00 and 19:00–21:00" stores as
  a single Monday total. If the planner later needs to place work at a time of day, that is an
  additive migration and a widened contract, not a correction.
- `available_minutes` accepts a value a learner could not sustain. Nothing judges a week, by design,
  so the only guard is that a day cannot exceed a day.

### Neutral

- Nothing reads availability yet. It is written and returned; no plan is built from it, which is the
  same position `stage_source` holds under ADR-017.
- `scripts.set_study_goal` is untouched. No command-line tool records availability.
- The seven days are never compared or weighted. A learner may give Sunday more time than Monday, and
  no code treats the week's order as a ranking.

## Alternatives considered

### `smallint` 0–6 with a documented convention

The literal reading of the approved schema, and the cheapest thing to sort in SQL. Zero would mean
Monday, matching Python's `date.weekday()` so the planner needs no mapping.

**Not selected:** it answers the open question rather than removing it, and the answer is invisible at
every point of use. A client that assumes `0` is Sunday — which JavaScript and PostgreSQL both do —
silently misfiles an entire week, and no constraint, type, or test can catch it. It would also make
`day_of_week` the only numeric enumerated value in a schema whose every other controlled value is
validated text.

### `smallint` stored, day name on the wire

Keeps the sortable column and gives the contract the safe form.

**Not selected:** it puts a translation layer between the column and the wire, which is exactly what
ADR-017 removed when it made the stored value and the wire value identical. The numbering would still
exist, in the one place a contributor is least likely to look.

### Clock-time ranges, several per day

`starts_at`/`ends_at`, no unique key on the day, so "Monday 06:00–08:00 and 19:00–21:00" stores
literally.

**Not selected:** nothing consumes a time of day. It would fix which timezone a wall-clock time is
read in before a planner exists to have an opinion, drop the unique key that makes "edit Monday"
well-defined, and oblige a client to address slots by identifier. Minutes per day is the smaller
promise, and widening it later is additive.

### Per-slot `POST`, `PATCH`, and `DELETE` endpoints

Matches "add, edit, and remove" literally, and suits a control that saves one day at a time.

**Not selected:** it replaces the catalogued GOAL-005 rather than implementing it, adds three public
endpoints plus a read where one suffices, and makes a week's edit several requests with no transaction
spanning them — a wider version of the partial-outcome problem ADR-016 recorded for the setup form's
two calls. No screen edits a single day in isolation.

### A separate `GET` endpoint for the saved week

`GET /study-goals/{id}/availability`, leaving the goal response unchanged.

**Not selected:** it adds an eighth endpoint and a further call to both screens, and leaves GOAL-003's
original intent line unfulfilled for no gain. The objection ADR-013 and ADR-017 raised against
embedding — that it makes reference data learner-owned — does not apply: a goal response is already
learner-owned, and availability hangs off the goal by foreign key.

### Refuse zero minutes and require the day to be omitted

One way to say "no time on Monday", so no client has to know that `0` and absent differ.

**Not selected:** it makes the approved `>= 0` constraint pointless, and it destroys a distinction the
learner can see the value of — a day deliberately kept free is a decision, and a day never considered
is not. ADR-017 kept the same distinction for the same reason.

### Report a weekly total on the response

A single number every screen wants, computed once where the days are already in hand.

**Not selected:** it is planning arithmetic over a planning input, and a total is the first step
toward the product having an opinion about whether a week is enough. FR-003's planner is what should
form that opinion, with the trade-offs visible, and it does not exist.

## Implementation notes

- Endpoint, request and response fields, and per-endpoint error codes are in
  [api/endpoints.md](../api/endpoints.md#learner-setup-and-goal-endpoints), which stays authoritative.
  No new error code was needed: `validation_error`, `not_found`, and `conflict` all existed.
- Migration `20260806_01_create_availability_slots_table` creates one empty table and alters nothing.
  The unique key it creates serves the only read there is, so no further index was added;
  [schema.md](../database/schema.md#required-indexes) lists none for this table.
- GOAL-005 is served by `ManageStudyGoals` rather than by a use case of its own, so the rule deciding
  whether a goal belongs to the effective learner stays in one place. `WEEKDAYS` and
  `MINUTES_IN_A_DAY` live in `application/dto/availability.py` and are mirrored by the model's `CHECK`,
  the same way `LEARNING_STAGES` is mirrored between `manage_topic_progress.py` and `progress.py`.
- Availability is read and written through `StudyGoalManagementRepository` rather than a port of its
  own: a slot has meaning only under its goal, is reached by a nested path, and is returned inside a
  goal response. The provider in `composition/providers.py` already owns the transaction and needed no
  change.
- The frontend is `features/onboarding/AvailabilityForm.tsx` with `availability.ts`, and
  `features/home/WeeklyAvailability.tsx`. `saveAvailability` joins `saveLearnerSetup` in the existing
  `"use server"` module, which still exports **only async functions** — the rule ADR-016 records and
  `frontend/tests/server-actions.test.ts` enforces, which is why the state shape lives in
  `availability.ts`.
- **Verified against the production standalone server with a contract-shaped stub API**, as ADR-015,
  ADR-016, and ADR-017 were. Thirty-three checks passed: `/setup` renders a control per named day and
  none named by an index; a no-JavaScript form submission produced exactly one `PUT` to the goal's
  availability carrying only the days entered, as `{"day_of_week": "monday", …}` with no `learner_id`;
  a day left blank was omitted, which removes it, while a `0` day was sent; the saved week was read
  back on `/setup` and on `/`, where an unset day is absent, a zero day reads *Kept free*, and no
  total appears; a day claiming 1500 minutes was refused in the page; and neither the API address nor
  `API_BASE_URL` appeared in the HTML of `/`, `/setup`, or `/curriculum`, nor in any of the eleven
  client scripts they load.
- **The PostgreSQL integration tests have not been run locally.** They are written —
  `tests/integration/test_availability_migration.py` and the GOAL-005 cases in
  `test_learner_onboarding_api.py` — and CI runs them; they skip on a workstation with no
  `TEST_DATABASE_URL`. The stub above proves the call topology and the contract, not the SQL.
- Open and deliberately not settled here: whether a slot ever gains a time of day, whether
  `planning_preferences` arrives with the planner or before it, and how a planner should behave when a
  week holds less time than a goal's horizon needs.
- Recorded as DEC-030 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](ADR-011-sqlalchemy-persistence-implementation.md) — the open `day_of_week` item this record retires, and the validated-text rule it follows
- [ADR-013: Model an examination period as a published window of reference data](ADR-013-examination-schedule-and-study-goal.md) — the record that held `availability_slots` back, and the reference-data separation this one departs from deliberately
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the envelope this contract answers in
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology the availability form inherits
- [ADR-016: Fix the learner setup API contracts](ADR-016-learner-onboarding-api-contracts.md) — the GOAL-005 deferral this record discharges
- [ADR-017: Record manual topic progress as a learner-owned stage](ADR-017-topic-progress-api-and-schema.md) — the stored-form rule and the absent-versus-explicit distinction this record reuses
- [ADR-019: Store planning preferences as typed columns replaced as a group](ADR-019-study-goal-planning-preferences.md) — the other half of FR-002's criterion, which reuses this record's replace-as-a-group and unset-versus-set rules
- [API conventions](../api/conventions.md) — the envelope, the error codes, and the `snake_case` rule
- [API endpoint catalog](../api/endpoints.md) — the contract this record decides
- [API versioning](../api/versioning.md) — what makes a change to it breaking
- [Database schema](../database/schema.md) — the approved target, and the column type this record changes
- [Database migrations](../database/migrations.md) — the migration this record introduces
- [Domain model](../domain/domain-model.md) — availability as a planning input
- [Domain entities](../domain/entities.md) — the availability slot entity
- [Terminology](../domain/terminology.md) — *availability slot* and *weekly availability*
- [Functional requirements](../requirements/functional.md) — FR-002, and the half of its criterion still unmet
- [Repository and folder structure](../development/folder-structure.md) — where the new modules live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 2 item this endpoint delivers
- [Architecture decision register](../architecture/decisions.md) — DEC-030
