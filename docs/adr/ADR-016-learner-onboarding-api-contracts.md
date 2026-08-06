---
title: "ADR-016: Fix the Learner Setup API Contracts"
status: accepted
owner: architecture-and-api
last_updated: 2026-08-06
related:
  - ../00-project-context.md
  - ../domain/terminology.md
  - ADR-009-configuration-naming-and-validation.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-013-examination-schedule-and-study-goal.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-018-weekly-availability-slots.md
  - ADR-019-study-goal-planning-preferences.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../api/versioning.md
  - ../database/schema.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../roadmap/future-ideas.md
  - ../architecture/decisions.md
---

# ADR-016: Fix the Learner Setup API Contracts

## Status

Accepted — 2026-08-05

Discharges the deferral [ADR-013](ADR-013-examination-schedule-and-study-goal.md) recorded, for six
of its seven endpoints. ADR-013 itself is unchanged and remains accepted.

**This record's file name retains "onboarding".** It was written before
[terminology](../domain/terminology.md#naming-rules) settled *learner setup* as the name of the
capability, and renaming an accepted ADR breaks every link that already points at it. The title above
uses the canonical term; the file name is a stable identifier, not vocabulary.

## Implementation status — 2026-08-05

*Note added 2026-08-05, later the same day. The decision below is unchanged: no endpoint was added, no
request or response field changed, and no status code moved. As elsewhere in this repository, the
accepted text is left as written.*

**These contracts now have a second client.** A home screen at `/` reads the learner's saved setup
back — LRN-001 for the profile, GOAL-002 for the goal, and EXM-001 for the cycle's dated periods —
and links to `/setup` to change it. It is read-only and writes nothing.

It needed **no new endpoint**, which is a consequence of two choices this record made. A goal response
carries the examination *window* but not the periods, and EXM-001 reports "every period beside it,
including the registration deadlines, which ADR-013 persisted precisely so the product could surface
them" — so a screen wanting those dates reads EXM-001 and matches the goal's cycle by id. The home
screen is the first thing to surface them.

It also inherits [ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md)'s call
topology without renegotiating it: the page is a React Server Component, the browser issues no request
to the backend, and `API_CORS_ALLOWED_ORIGINS` stays planned rather than implemented.

**Two statements are overtaken:**

- Under [Neutral](#neutral), "The contracts are implemented by one client, the setup screen." Two
  clients implement them now. The same bullet's next sentence — "Later screens inherit them" — is what
  actually happened, so the position is unchanged; only the count is.
- The acceptance-criteria arithmetic. Under [Positive](#positive), "Two of FR-002's four acceptance
  criteria are met", and under [the decision](#the-deferral-is-discharged-for-lrn-001-lrn-002-and-goal-001-to-goal-004),
  "Two of FR-002's four acceptance criteria are accordingly still unmet".
  [FR-002](../requirements/functional.md#fr-002-initial-learner-setup) has since gained a fifth
  criterion — reviewing the saved setup without re-entering it — which the home screen meets. **Three
  of five are now met.** The two that are not are exactly the two this record named, unchanged and
  waiting on the same work: weekly availability, which needs the `day_of_week` decision, and receiving
  an initial plan, which needs Milestone 3.
  [endpoints.md](../api/endpoints.md#fr-002-acceptance-criteria) carries the current count and stays
  authoritative for it.

## Implementation status — 2026-08-06

*Note added 2026-08-06. The decision below is unchanged: no implemented endpoint was added or removed,
no request field changed, and no status code moved. As elsewhere in this repository, the accepted text
is left as written.*

**GOAL-005 is implemented, so the one deferral this record kept is discharged.**
[ADR-018](ADR-018-weekly-availability-slots.md) creates `availability_slots` and fixes GOAL-005's
contract. The schema decision this record identified as the blocker — "creating it would fix the
`day_of_week` numbering convention ADR-011 records as an open project-owner decision" — was taken
deliberately rather than as a side effect of a form, which is what
[the alternative this record rejected](#implement-goal-005-alongside-the-rest) asked for. It was
**retired rather than chosen**: the column stores a day name, so no numbering exists.

**Three statements are overtaken:**

- Under [the decision](#the-deferral-is-discharged-for-lrn-001-lrn-002-and-goal-001-to-goal-004),
  "GOAL-005 stays deferred, for a different reason." It no longer does.
- **The acceptance-criteria arithmetic, again.** The criterion this record counted as unmet — "The
  learner can set available study time and basic planning preferences" — is now **partly met**:
  available study time is set through GOAL-005, and planning preferences remain unaccepted because
  `study_goals.planning_preferences` is not created, which is the same reason GOAL-004 gives.
  Receiving an initial plan is still unmet and still waits on Milestone 3.
  [endpoints.md](../api/endpoints.md#fr-002-acceptance-criteria) carries the current count.
- **A goal response gained a field.** `availability` now travels on GOAL-001 to GOAL-004, which
  discharges the availability summary GOAL-003's catalogue entry originally promised and this record
  explicitly withheld. It is a compatible addition under
  [versioning](../api/versioning.md#compatible-changes-within-a-major-version), and no existing field
  changed.

**Two of this record's positions were inherited rather than renegotiated,** which is what it says
later screens do: the write goes through the same `"use server"` module — which still exports only
async functions — and the backend still gains no CORS.

## Implementation status — 2026-08-06, later the same day

*Note added 2026-08-06. The decision below is unchanged: no endpoint was added or removed, no existing
field changed, and no status code moved. As elsewhere in this repository, the accepted text is left as
written.*

**GOAL-004 now accepts planning preferences,** which this record explicitly withheld.
[ADR-019](ADR-019-study-goal-planning-preferences.md) creates the two columns to hold them and fixes
the contract; GOAL-001 accepts them too, and every goal response carries them. Both are compatible
additions under [versioning](../api/versioning.md#compatible-changes-within-a-major-version).

**Three statements are overtaken:**

- Under [the decision](#a-partial-update-leaves-unmentioned-fields-alone-and-an-explicit-null-clears),
  the absent-versus-`null` rule is now joined by a **group** rule that record did not need: a supplied
  `planning_preferences` object replaces the stored group whole, so a member left out of it is unset.
  The scalar rule is unchanged, and ADR-019 records why a group needs the different one — a form shows
  every preference at once, so a control the learner cleared has to reach the API as a clearance.
- **The acceptance-criteria arithmetic, a third time.** The criterion the 2026-08-06 note above reported
  as partly met — "The learner can set available study time and basic planning preferences" — is now
  **met in full**. [endpoints.md](../api/endpoints.md#fr-002-acceptance-criteria) carries the count.
- The `Neutral` bullet about client count is overtaken again in the same direction as before: the
  preference controls are a fieldset on the setup screen the two existing clients already share.

**This record's positions were again inherited rather than renegotiated:** the write goes through the
same `"use server"` module, which still exports only async functions, the backend still gains no CORS,
and `scripts.set_study_goal` still keeps its own port — it copies a stored preference across rather than
managing one.

## Context

[ADR-013](ADR-013-examination-schedule-and-study-goal.md) deferred LRN-001, LRN-002, and GOAL-001 to
GOAL-005 on one condition: their request and response schemas are written "when the frontend that
consumes them exists, so a contract is not fixed ahead of its first caller."

Its implementation-status note of 2026-08-03 recorded that the condition had become ambiguous. A
frontend application existed, per [ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md),
but no screen that would consume these endpoints did — and "whether the deferral's condition means an
application exists or a *screen for these endpoints* exists is precisely what has to be settled." It
named the deferral "the next decision in this area rather than a position that continues by default".

Building the learner setup screen settles it under either reading. What remained open was narrow,
because [ADR-014](ADR-014-api-response-contract.md) had already fixed the envelope, the pagination
block, and the error catalogue: only the **fields** were undecided.

Four further questions surfaced while writing them, none with a recorded answer:

1. **How a learner chooses an examination cycle.** ADR-013 stated that "an examination window reaches
   a client through a goal response", which is circular for a learner who has no goal yet. Nothing
   exposed the published schedules, so the first goal could only be set by typing a cycle label.

2. **What a read returns before setup has run.** `learners` is empty on a fresh installation. A
   profile endpoint must answer something, and `404`, an empty object, and auto-creating a learner
   are materially different promises.

3. **Whether creating a goal replaces an existing one.** The `scripts.set_study_goal` command
   deliberately upserts the learner's active goal. An HTTP `POST` doing the same would make a
   double-submitted form silently discard the goal a plan was built from.

4. **Whether the browser gains a direct route to the API.** ADR-015 forbids acquiring a CORS
   allow-list *incidentally*. Learner setup is the first write in the product, so this was the first
   feature that could have.

## Decision

### The deferral is discharged for LRN-001, LRN-002, and GOAL-001 to GOAL-004

Their contracts are fixed and catalogued in [api/endpoints.md](../api/endpoints.md#learner-setup-and-goal-endpoints),
which stays the document a contributor reads. This record holds the rationale and is not rewritten as
the endpoints grow.

**GOAL-005 stays deferred, for a different reason.** Replacing weekly availability needs
`availability_slots`, which does not exist: creating it would fix the `day_of_week` numbering
convention [ADR-011](ADR-011-sqlalchemy-persistence-implementation.md) records as open and no
requirement yet constrains. That is a schema decision, not a contract one, so a caller's existence
does not unblock it. Two of FR-002's four acceptance criteria are accordingly still unmet — weekly
availability, and receiving an initial plan, the second of which needs Milestone 3's planning work
rather than anything this record decides. [endpoints.md](../api/endpoints.md#fr-002-acceptance-criteria) names
both rather than leaving them to be inferred.

### EXM-001 exposes the published schedules, as reference data

`GET /api/v1/examination-schedules`, filterable by `learning_program_id`, paginated like every other
collection. It resolves no learner identity, because a schedule describes the world rather than the
learner.

It reports the **window** — first sitting day to last, derived from the `examination` periods — and
never a single examination date. It reports every period beside it, including the registration
deadlines, which ADR-013 persisted precisely so the product could surface them. Provenance travels
with the dates: the organising body, the source, the day it was read, and `schedule_status`.

A new endpoint identifier rather than a field on CUR-002: a curriculum and an examination calendar
change on different cadences, which is the same separation ADR-013 made in the schema.

### A read never writes, and an absent learner is `data: null`

LRN-001 returns `200` with `data: null` when no learner is stored. A `404` would report a missing
*endpoint-addressed record* for what is an ordinary state of a fresh installation, and a client would
have to special-case it before setup and after. Auto-creating on a `GET` would let a page load leave
a record behind.

The learner is created by LRN-002, on the learner's own action. Its timezone defaults to
`APP_DEFAULT_TIMEZONE` — the value [ADR-013](ADR-013-examination-schedule-and-study-goal.md) settled —
supplied by the composition root, because application code reads no configuration
([ADR-009](ADR-009-configuration-naming-and-validation.md)).

### A partial update leaves unmentioned fields alone, and an explicit `null` clears

`PATCH` semantics throughout. A form that omitted the timezone must not reset it: a timestamp read in
the wrong zone is wrong by a day at the boundary, which is where a study plan's dates land.

Absence and `null` are therefore given different meanings, because one cannot express both. `null`
clears a field the learner may legitimately want empty — `display_name`, `target_date`,
`examination_schedule_id` — and is rejected for a field that must always hold a value: `timezone` and
`status`. A rejection is better than a silent no-op, which is what treating them alike would produce.

### A goal binds to the program's active curriculum version, and the request cannot name one

GOAL-001 accepts `learning_program_id`, not `curriculum_version_id`. A client chooses what it is
studying, not which revision of the syllabus; accepting a version identifier would let a learner be
attached to a `draft` or `retired` one. An existing goal keeps the version it was created against,
even after that version retires, because it records what the learner actually planned against.

Accepting `curriculum_version_id` later is a compatible change under
[versioning](../api/versioning.md#compatible-changes-within-a-major-version).

### A second active goal for the same program is a `409`, not a replacement

`POST` creates, per [conventions](../api/conventions.md#http-methods-and-status-codes). The existing
active goal is what any plan was built from, so a double-submitted form must not overwrite it.
Editing goes through GOAL-004. Paused, completed, and archived goals are history and do not conflict.

This deliberately differs from `scripts.set_study_goal`, which upserts. That is right for an
idempotent command a contributor re-runs and wrong for a request a browser can repeat, so the command
keeps its behaviour and its own narrower port.

### `409` gains the code `conflict`

The first status the API returns deliberately that had no entry in ADR-014's catalogue. Three
conditions produce it: an active goal already exists for the program, no learner exists yet to own a
goal, or more than one learner is stored so the local learner is undefined.

Each is a request refused for what is already stored rather than for its shape, which is why none is
a `422`: there is no offending field to name, and a client's remedy is to change the state — create
the profile, or edit the existing goal — not to correct its input. The full list lives in
[conventions.md](../api/conventions.md#error-codes), which ADR-014 names authoritative for the
catalogue. Compatible, because `409` previously fell back to `request_failed`.

### A goal not owned by the effective learner is reported as `404`

Not `403`. `conventions.md` treats "not visible to the caller" as a `404`, and confirming that a
record exists but belongs to someone else leaks its existence. It cannot arise today — LearnFlow is
single-learner — but the rule is written now so authentication does not have to introduce it.

### The setup screen writes through a Next.js server action, and the backend gains no CORS

The form posts to the Next.js server, which calls the API with the same server-side `API_BASE_URL`
the curriculum views use. The browser still issues no request to the backend, so
`API_CORS_ALLOWED_ORIGINS` stays planned rather than implemented.

This inherits [ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md) rather than
renegotiating it, which is what that record says every later screen does. A setup form has no
interaction a server round trip cannot serve, so an allow-list here would exist solely because of how
the page was written — exactly what ADR-015 forbids acquiring incidentally.

## Consequences

### Positive

- A learner can complete setup end to end: name, timezone, learning program, and a horizon, with the
  examination shown as a window carrying its source and its provisional status.
- Two of FR-002's four acceptance criteria are met, and the two that are not are named with the work
  each waits on rather than left to be inferred.
- The `learner-planning` and `examination schedule` first-API-contract reviews in
  [schema.md](../database/schema.md) are discharged, and **neither needed a schema change** — the
  tables ADR-013 created hold everything these contracts return.
- No migration, so no learner data is reinterpreted.
- The API's exposure surface is unchanged by the arrival of the first write path: no CORS, no
  browser-visible API address.

### Negative

- Seven endpoints are now public contract — the six whose deferral this record discharges, plus
  EXM-001, which it adds. Changing a field or a status code on any of them is breaking under
  [versioning](../api/versioning.md#breaking-changes), where before there was nothing to break.
- The setup form makes two API calls, so a goal that fails leaves an updated profile behind. There is
  no transaction spanning them, and inventing one would mean an endpoint that writes both. The
  frontend reports the partial outcome instead of hiding it.
- `POST` refusing a second active goal means a learner switching programs must archive or update the
  first. That is a real step the UI does not yet offer.
- Deriving the examination window on every read costs a query per schedule, and reading a page of
  goals reads each goal's periods separately. At a handful of goals this does not matter; a stored
  window would be faster and would drift.

### Neutral

- The contracts are implemented by one client, the setup screen. Later screens inherit them.
- `scripts.set_study_goal` is untouched and keeps its own port, so the command and the endpoints do
  not share a repository interface even though they share tables.
- The rule deciding the examination window now lives in one application module, called by both the
  command and the endpoints, so the two cannot disagree about when the examination is.

## Alternatives considered

### Return `404` from LRN-001 before a learner exists

**Not selected:** it reports a missing record for an ordinary state of a fresh installation, and a
client would need one branch before setup and another after, for the same endpoint.

### Create the learner on the first `GET`

**Not selected:** a read that writes means a page load, a health probe, or a crawler leaves a learner
record behind. Creation belongs to the action the learner took.

### Let `POST /api/v1/study-goals` upsert the active goal

The command already does this, and it would make the setup form idempotent for free.

**Not selected:** `POST` creates under the approved conventions, and a browser can repeat a request
in ways a command-line run cannot. Silently replacing the goal a plan was built from is data loss
dressed as convenience.

### Expose examination schedules as a field on CUR-002

No new endpoint, and a compatible addition to an implemented contract.

**Not selected:** it couples a syllabus to an examination calendar, which ADR-013 separated because
they change on different cadences. It would also grow the curriculum response for every client,
including those that do not care about dates.

### Accept `curriculum_version_id` on GOAL-001

The catalogue's original intent line said "program/version".

**Not selected:** no client has a reason to choose a version, and accepting one lets a goal bind to a
`draft` or `retired` syllabus with no rule to stop it. It can be added compatibly when a reason
appears.

### Have the browser call the API directly for the write

The conventional form-submission shape: a client component `fetch`es the backend.

**Not selected:** it requires CORS middleware, an allow-list variable, and a browser-visible API
address, and it would fix an origin policy before any authenticated or learner-owned endpoint exists
whose exposure could be reasoned about. ADR-015 permits this only for a feature that genuinely needs
it; a setup form does not.

### Implement GOAL-005 alongside the rest

It is the remaining half of FR-002.

**Not selected:** it needs `availability_slots`, and creating that table fixes the `day_of_week`
numbering convention ADR-011 records as an open project-owner decision. Choosing it as a side effect
of a form is exactly what ADR-011 exists to prevent.

## Implementation notes

- Endpoints, request and response fields, and per-endpoint error codes are in
  [api/endpoints.md](../api/endpoints.md#learner-setup-and-goal-endpoints), which stays authoritative.
  The `conflict` code is in [api/conventions.md](../api/conventions.md#error-codes).
- Use cases are `manage_learner_profile.py`, `manage_study_goals.py`, and
  `read_examination_schedules.py`; `examination_window.py` holds the window derivation both they and
  `set_study_goal.py` call, and `local_learner.py` resolves the effective learner. Routes are
  `presentation/api/routes/learner.py`, `study_goals.py`, and `examination_schedules.py`.
- The learner-owned providers in `composition/providers.py` own the transaction: they commit when the
  request completes and roll back when it raises, so no route reports a failure over committed work.
  `tests/unit/test_providers.py` and `tests/api/test_provider_transactions.py` hold that to account.
- **No migration.** The tables ADR-013 created are unchanged.
- The frontend is `app/setup/` and `features/onboarding/`. `actions.ts` is a `"use server"` module and
  exports **one async function and nothing else** — a constant exported from such a module fails at
  runtime with a `500` that neither `tsc` nor `next build` reports. `tests/server-actions.test.ts`
  enforces it; the failure was found by running the built server, not by reading the code, which is
  the same way ADR-015 found its loading-boundary trap.
- Verified against the production standalone server with a contract-shaped stub API: the setup screen
  renders, a no-JavaScript form submission creates the profile and the goal, a resubmission updates
  them without creating a second goal, a rejected field and a `409` are both reported in the page, and
  no API address appears in the served HTML or in any client script.
- Open and deliberately not settled here: GOAL-005 and the `day_of_week` convention, and whether a
  learner may hold active goals for more than one learning program at a time.
- Two things this record deliberately does **not** add, each recorded with its trigger in
  [deferred ideas](../roadmap/future-ideas.md):
  - **A database constraint for "one active goal per program."** The rule lives in the use case. A
    partial unique index would make it structural, but no writer today can race another into breaking
    it, and the index would make `scripts.set_study_goal`'s upsert fail where it currently succeeds.
  - **A screen for switching learning programs.** The capability exists over HTTP — GOAL-004 pauses
    or archives a goal, after which GOAL-001 accepts a new one — but no UI offers it, so today it
    means editing a goal by hand. Designing that screen needs the multi-program question above
    answered first.
- Recorded as DEC-028 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-009: Name and validate configuration variables explicitly](ADR-009-configuration-naming-and-validation.md) — why the default timezone reaches the use case from the composition root
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](ADR-011-sqlalchemy-persistence-implementation.md) — the `day_of_week` decision GOAL-005 waited on
- [ADR-018: Store weekly availability as named days replaced a week at a time](ADR-018-weekly-availability-slots.md) — the record that takes that decision and discharges the GOAL-005 deferral this one kept
- [ADR-019: Store planning preferences as typed columns replaced as a group](ADR-019-study-goal-planning-preferences.md) — the record that adds to GOAL-004 the planning preferences this one withheld, and the group-replace rule it needed
- [ADR-013: Model an examination period as a published window of reference data](ADR-013-examination-schedule-and-study-goal.md) — the deferral this record discharges, and the window rule it implements
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the envelope and catalogue these contracts answer in
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology the setup screen inherits
- [API conventions](../api/conventions.md) — the `conflict` code this record adds
- [API endpoint catalog](../api/endpoints.md) — the contracts this record decides
- [API versioning](../api/versioning.md) — what makes a change to them breaking
- [Database schema](../database/schema.md) — the first-API-contract reviews this record discharges
- [Terminology](../domain/terminology.md) — the examination vocabulary these responses use
- [Functional requirements](../requirements/functional.md) — FR-002, and the criterion still unmet
- [Repository and folder structure](../development/folder-structure.md) — where the new modules live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 2 items these endpoints deliver
- [Deferred ideas](../roadmap/future-ideas.md) — the constraint and the program-switch screen this record leaves out, with their triggers
- [Terminology](../domain/terminology.md) — *learner setup*, the canonical name for the capability these endpoints serve
- [Architecture decision register](../architecture/decisions.md) — DEC-028
