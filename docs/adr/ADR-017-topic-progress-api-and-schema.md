---
title: "ADR-017: Record Manual Topic Progress as a Learner-Owned Stage"
status: accepted
owner: architecture-and-api
last_updated: 2026-08-05
related:
  - ../00-project-context.md
  - ADR-008-assessment-and-mistake-evidence-model.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-016-learner-onboarding-api-contracts.md
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

# ADR-017: Record Manual Topic Progress as a Learner-Owned Stage

## Status

Accepted — 2026-08-05

This is the first **learner topic progress** LearnFlow stores. Learner setup records what a learner
intends; this records how far along they judge themselves to be.

It stores a *stage*, not *evidence*. [Terminology](../domain/terminology.md#naming-rules) reserves
**evidence** for observed learning signals — study activity, quiz outcomes, external test results,
mistakes — and **stage** for the learner-visible interpretation of them. Nothing here observes
anything: the learner states the interpretation directly, and the evidence that would otherwise
support it does not exist yet. `stage_source` is what records that difference.

## Context

[FR-005](../requirements/functional.md#fr-005-topic-progress-and-learning-evidence) requires a
learner to mark a topic with one of five learning stages and to change it at any time.
[Milestone 2](../roadmap/milestones.md#milestone-2-learner-setup-and-progress-baseline) carries the
same item. Nothing implemented it: `docs/api/endpoints.md` catalogued PRG-001 to PRG-004 and ACT-001
to ACT-002 as intent lines with no request or response fields, and the *Progress and revision* schema
area had no migration.

Five things were undecided, and the first line of code could avoid none of them.

1. **How the five stages are stored and sent.** [terminology](../domain/terminology.md) and
   [entities](../domain/entities.md) fix the labels — *Not explored*, *Building foundation*,
   *Developing confidence*, *Practice-ready*, *Strong understanding* — as learner-facing prose. No
   document said what goes in a column or on a wire.

2. **What "Not explored" is.** It is documented as the neutral starting state. Whether that is a
   stored value, the absence of a record, or both is a different promise in each case, and it decides
   whether a fresh installation holds zero progress rows or one per trackable topic.

3. **How much of `learner_topic_progress` to create.** [schema.md](../database/schema.md#learner_topic_progress)
   approves eight columns. This feature reads and writes two of them.

4. **Which of the six progress endpoints to contract.** Only two are needed to mark a stage and show
   it back.

5. **Whether the browser gains a direct route to the API.** This is the second write in the product,
   and the first one a learner performs repeatedly while reading a page.

## Decision

### PRG-004 records a stage; PRG-002 reads back what was recorded

`PATCH /api/v1/progress/topics/{topic_id}` and `GET /api/v1/progress/topics`. Their fields and
per-endpoint errors are catalogued in
[api/endpoints.md](../api/endpoints.md#progress-and-study-activity-endpoints), which stays the
document a contributor reads. This record holds the rationale and is not rewritten as the endpoints
grow.

**PRG-001, PRG-003, ACT-001, and ACT-002 stay uncontracted**, each for a reason of its own rather
than for lack of time. PRG-001 reports the current plan, revisions due, and priority focus areas —
none of which exists. PRG-003 promises "evidence and next action", and no evidence is stored at all —
only the stage — so the endpoint would differ from PRG-002 by nothing. ACT-001 and ACT-002 need
`study_activities`. Fixing a contract before its first caller is what
[ADR-013](ADR-013-examination-schedule-and-study-goal.md)'s deferral rule exists to prevent.

PRG-002 accepts `curriculum_version_id` and the standard window. `subject_id` and `learning_stage`
filters, which the catalogue's intent line also names, are compatible additions under
[versioning](../api/versioning.md#compatible-changes-within-a-major-version) and are left to the
screen that needs them. `material_status` is not offered at all, because the column is not created.

### The stored form is `snake_case`; the label is presentation

`not_explored`, `building_foundation`, `developing_confidence`, `practice_ready`, and
`strong_understanding` in the database, in the `CHECK` constraint, and on the wire. Every other
controlled value in the schema is spelled this way — `late_registration`, `recommended_before`,
`review_mistakes` — and [conventions](../api/conventions.md#json-naming-and-data-formats) requires
enumerated fields to use the canonical vocabulary, not the canonical typography.

The label a learner reads stays in the client. A copy-edit to *Practice-ready* must be a text change,
not a migration over learner rows.

### Absence means "Not explored"; a read never writes

A topic with no row has no recorded stage, and the interface shows *Not explored*. Setting
`not_explored` explicitly is accepted and stores a row, so a learner who deliberately reset a topic
stays distinguishable from one who never opened it.

The alternative — creating a row per trackable topic — would mean a page load, or setup, leaving one
learner-owned record per trackable topic behind for a learner who has recorded nothing. That is the
same objection
[ADR-016](ADR-016-learner-onboarding-api-contracts.md) raised against creating the learner on a
`GET`, and it holds here for the same reason.

### There is no way to clear a stage

`learning_stage` is required, and `null` is rejected rather than treated as a clear. ADR-016 gave
absence and `null` different meanings so a partial update could express both; here there is one
field, it always holds a value, and the field-level `null` that would express "remove this" could
only mean deleting the row. Deleting learner-owned data through a field update is a destructive
operation wearing a `PATCH`'s clothes.

A learner who has changed their mind records `not_explored`.

### The migration creates five columns of the eight, and `stage_source` is one of them

`learner_topic_progress` is created with `id`, `learner_id`, `topic_id`, `learning_stage`,
`stage_source`, and the audit timestamps. `material_status`, `material_completed_at`, and
`last_studied_at` are **not** created: the first two belong to material completion, which nothing
records, and the third can only be filled from a study activity, and `study_activities` does not
exist. Each arrives with the change that writes it, per
[ADR-011](ADR-011-sqlalchemy-persistence-implementation.md). Adding a nullable column to this table
later is the additive migration [migrations.md](../database/migrations.md#additive-changes-first)
prefers.

`stage_source` is deliberately **not** deferred, though every row written today says `learner` and
nothing derives a stage. FR-005 requires that the product not claim mastery from one signal, and
telling a learner's own answer from a derived one is what makes that enforceable. Adding the column
after evidence starts proposing stages would mean backfilling rows whose origin is no longer
recoverable — the one case where "wait for the code that reads it" produces a worse outcome than
creating the column now.

### A grouping topic is refused with a `422`, in the application

`topics.is_trackable` already says whether progress can be recorded directly against a topic, and a
topic that merely groups subtopics cannot. The rule is enforced by the use case rather than by a
constraint: it is about what a topic *is*, and a database check would have to reach across a foreign
key to find out.

The refusal names `path.topic_id`, so a client can say which control was wrong.

### The curriculum page joins two responses; CUR-003 is unchanged

A learner sees the saved stage while browsing the curriculum, so the program page reads CUR-003 and
PRG-002 together and matches them by topic identifier. The two calls run concurrently — neither
addresses the other's result, so the page waits once instead of twice.

**CUR-003 gains no `learning_stage` field.** It serves reference data and resolves no learner, and
adding a learner-owned field would make every curriculum read learner-owned, for every client
including those that do not care. That is the same separation
[ADR-013](ADR-013-examination-schedule-and-study-goal.md) made when it refused to hang the
examination calendar off CUR-002.

A failure of PRG-002 alone is not fatal to the page. The curriculum still renders, without the
controls: the syllabus is what every reader can see, and one learner's stages should not be able to
take it away.

### The write goes through a Next.js server action, and the backend gains no CORS

Each trackable topic carries a small form posting to a `"use server"` module, which calls the API
with the same server-side `API_BASE_URL` every other view uses. The browser still issues no request
to the backend, so `API_CORS_ALLOWED_ORIGINS` stays planned rather than implemented.

This inherits [ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md) and
[ADR-016](ADR-016-learner-onboarding-api-contracts.md) rather than renegotiating them. A select and a
save button have no interaction a server round trip cannot serve, and the form works without
JavaScript.

## Consequences

### Positive

- FR-005's first, third, and sixth acceptance criteria are met: a learner can mark a topic with one
  of the five stages, change it at any time, and is shown a next action rather than a label alone.
- Every stage is stored with its origin from the first row, so the boundary FR-005 draws between a
  learner's own claim and a stage derived from evidence is enforceable rather than aspirational.
- No implemented contract changed. CUR-001 to CUR-003, LRN-001, LRN-002, GOAL-001 to GOAL-004, and
  EXM-001 are untouched, so nothing is breaking under [versioning](../api/versioning.md).
- The API's exposure surface is unchanged by a second write path: no CORS, no browser-visible API
  address.
- The migration creates one empty table and alters nothing, so no learner data is reinterpreted.

### Negative

- Two more endpoints are public contract. Changing a field or a status code on either is breaking.
- The curriculum program page now makes three API calls where it made two, and it became a
  learner-owned page: it renders differently for a learner who has completed setup and one who has
  not.
- Every trackable topic carries its own form, so a large curriculum renders many controls. The
  curated GATE CSE curriculum has 65 topics and subtopics, of which the trackable leaves fit in one
  PRG-002 page at the maximum `limit` of 100. A curriculum larger than that would need the page to
  page through progress, and the `pagination` block is what would reveal it.
- Saving a stage is a round trip and a re-render, not an inline update. That is the cost of the call
  topology, and it is the cost ADR-015 accepted deliberately.
- `learner_topic_progress` now exists with three approved columns absent, so the table and
  [schema.md](../database/schema.md#learner_topic_progress) do not match until those arrive. The
  schema document records which, and why.

### Neutral

- Nothing reads `stage_source` yet. It is written and returned; no rule branches on it.
- The five stages are never compared. A learner may move to any stage from any stage, including
  backwards, and no code treats the order as a ranking.
- `scripts.set_study_goal` is untouched. No command-line tool records progress.

## Alternatives considered

### Store the display labels verbatim

`Practice-ready` in the column and on the wire. No mapping layer, and one spelling to keep in step.

**Not selected:** it breaks the `snake_case` convention every other controlled value follows, and it
makes learner-facing copy load-bearing. Rewording a label would become a migration over learner rows.

### Create a progress row for every trackable topic

Uniform reads: every topic has a record, and the client needs no join or fallback.

**Not selected:** it writes a learner-owned row per trackable topic for a learner who has recorded
nothing, and the natural trigger for it is a page load or a setup step — a read that writes, which ADR-016 refused for
LRN-001 on the same grounds. It also destroys the distinction between a topic never touched and one
deliberately reset.

### Add `learning_stage` to CUR-003

One call for the curriculum page, and a compatible addition to an implemented contract.

**Not selected:** it makes reference data learner-owned. CUR-003 resolves no learner today and is the
same for every reader; adding a stage would oblige it to, and would grow the response for clients
that do not want it. ADR-013 made the same separation between a syllabus and an examination calendar.

### Create the whole documented `learner_topic_progress` table

It is approved in full, and it avoids a second migration later.

**Not selected:** `last_studied_at` cannot be maintained without `study_activities`, and
`material_status` has no writer. A column nothing fills is one a reader will eventually trust. ADR-011
exists to prevent exactly this.

### Defer `stage_source` with the other three columns

Consistent with the rule applied to its neighbours, and every value today would be the same.

**Not selected:** it is the one column whose *absence* cannot be repaired later. Once quiz or
external-test evidence proposes a stage, no backfill can recover which existing rows a learner set
themselves — and FR-005's rule against claiming mastery from one signal depends on knowing.

### Implement PRG-003 alongside PRG-002

The catalogue lists it, and a per-topic detail view is a natural read.

**Not selected:** it promises "progress summary, evidence, and next action". No evidence is stored,
and the next action is presentation, so the endpoint would return what PRG-002 already returns per
item. It arrives with the evidence that gives it something to say.

### Let the browser call the API directly for the write

An inline save with no navigation, which suits a control repeated down a long page.

**Not selected:** it requires CORS middleware, an allow-list variable, and a browser-visible API
address. ADR-015 permits that only for a feature that genuinely needs it, and a select with a save
button does not.

## Implementation notes

- Endpoints, request and response fields, and per-endpoint error codes are in
  [api/endpoints.md](../api/endpoints.md#progress-and-study-activity-endpoints), which stays
  authoritative. No new error code was needed: `validation_error`, `not_found`, and `conflict` all
  existed.
- The use case is `manage_topic_progress.py`, working through `topic_progress_repository.py`.
  `local_learner.py` resolves the effective learner, as it does for every learner-owned endpoint. The
  route is `presentation/api/routes/progress.py`.
- The provider in `composition/providers.py` owns the transaction, as the other learner-owned
  providers do: it commits when the request completes and rolls back when it raises.
  `tests/unit/test_providers.py` and `tests/api/test_provider_transactions.py` hold that to account,
  including that a refused stage leaves no record behind.
- Migration `20260805_01_create_learner_topic_progress_table` creates one empty table and alters
  nothing.
- The frontend is `features/progress/`. `actions.ts` is a `"use server"` module exporting one async
  function and nothing else — the rule
  [ADR-016](ADR-016-learner-onboarding-api-contracts.md) records, which
  `frontend/tests/server-actions.test.ts` enforces. The stage state shape lives in `submission.ts`
  for that reason.
- **Verified against the production standalone server with a contract-shaped stub API**, as ADR-015
  and ADR-016 were. Twenty-three checks passed: the curriculum view renders a stage control against
  each trackable topic and none against a grouping one; an unrecorded topic shows *Not explored*; a
  no-JavaScript form submission creates the stage and a second one updates it, both reaching PRG-004
  as `{"learning_stage": ...}` with no `learner_id`; the saved stage and its next action are read
  back on the next page load; and neither the API address nor `API_BASE_URL` appears in the HTML of
  `/`, `/curriculum`, `/setup`, or the program page, nor in any of the eleven client scripts they
  load. The two writes produced exactly two `PATCH` requests to one topic, so an update rewrites a
  record rather than creating a second.
- **The PostgreSQL integration tests have not been run locally.** They are written and CI runs them;
  they skip on a workstation with no `TEST_DATABASE_URL`. The stub above proves the call topology and
  the contract, not the SQL.
- Open and deliberately not settled here: when `material_status` arrives and what records it, whether
  a derived stage may overwrite a learner's own, and whether the progress overview PRG-001 serves is
  a screen of its own or a section of the home screen.
- Recorded as DEC-029 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-008: Model assessment topics and mistake evidence sources explicitly](ADR-008-assessment-and-mistake-evidence-model.md) — the evidence boundaries a derived stage will have to respect
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](ADR-011-sqlalchemy-persistence-implementation.md) — the rule the three deferred columns follow, and the one `stage_source` is excepted from
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the envelope and error catalogue these contracts answer in
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology the stage control inherits
- [ADR-016: Fix the learner setup API contracts](ADR-016-learner-onboarding-api-contracts.md) — the server-action write path and the `null`-versus-absence rule this record follows
- [API conventions](../api/conventions.md) — the envelope, the error codes, and the `snake_case` rule
- [API endpoint catalog](../api/endpoints.md) — the contracts this record decides
- [API versioning](../api/versioning.md) — what makes a change to them breaking
- [Database schema](../database/schema.md) — the approved target, and which columns are not yet created
- [Database migrations](../database/migrations.md) — the migration this record introduces
- [Domain model](../domain/domain-model.md) — learner topic progress, and what a learning stage is not
- [Terminology](../domain/terminology.md) — the five stage labels the stored values map onto
- [Functional requirements](../requirements/functional.md) — FR-005, and the criteria still unmet
- [Repository and folder structure](../development/folder-structure.md) — where the new modules live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 2 item these endpoints deliver
- [Architecture decision register](../architecture/decisions.md) — DEC-029
