---
title: "ADR-019: Store Planning Preferences as Typed Columns Replaced as a Group"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-06
related:
  - ADR-020-initial-study-plan-generation.md
  - ../00-project-context.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-013-examination-schedule-and-study-goal.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-016-learner-onboarding-api-contracts.md
  - ADR-017-topic-progress-api-and-schema.md
  - ADR-018-weekly-availability-slots.md
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

# ADR-019: Store Planning Preferences as Typed Columns Replaced as a Group

## Status

Accepted — 2026-08-06

This record completes [FR-002](../requirements/functional.md#fr-002-initial-learner-setup)'s second
acceptance criterion, whose other half [ADR-018](ADR-018-weekly-availability-slots.md) delivered. It
also answers the last thing [ADR-013](ADR-013-examination-schedule-and-study-goal.md) left open in the
learner-planning area: `study_goals.planning_preferences`, which that record held back because
"nothing reads it, and its shape is undecided."

## Implementation status — 2026-08-06, later the same day

*Note added 2026-08-06, later the same day. The decision below is unchanged: the two typed columns,
the replace-as-a-group rule, and the unset-is-not-a-default rule are all untouched.*

**The preferences are now consumed.** [ADR-020](ADR-020-initial-study-plan-generation.md) generates a
study plan from them, and **FR-002 is met in full** —
[endpoints.md](../api/endpoints.md#fr-002-acceptance-criteria) carries the count and stays
authoritative for it.

**Five statements are overtaken:**

- The section heading *Nothing consumes, ranks, or scores a preference*, and its text "No plan is
  generated … Milestone 3's planner is what reads them". Nothing still **ranks or scores** a
  preference; a plan now **consumes** both.
- "The home screen says so in the page." That copy has been replaced: the panel now says what a plan
  does with a preference.
- Under [Positive](#positive), "four of its five criteria are met and one — receiving an initial plan
  — remains".
- Under [Positive](#positive), "The learner-planning schema area is now complete except for
  `study_plans` and `plan_items`". Both now exist.
- Under [Negative](#negative), "A preference can be saved that no plan will honour for as long as no
  plan exists", and under [Neutral](#neutral), "Nothing reads a preference yet."

**The risk this record recorded did not materialise.** It warned that fixing the shape before a
planner existed might prove wrong — "a planner may find that a session length wants a range rather
than a single value, or that a topic order needs a third choice". The planner needed neither: a single
session length was exactly what placing work on a day required, and both topic orders were
implementable. One thing it could not have known did surface: **the curated curriculum stores no
prerequisite link**, so `prerequisites_first` yields syllabus order today, and the plan says so rather
than implying otherwise. That is a curriculum-data gap, not a contract defect.

## Context

FR-002 requires a learner to "set available study time and basic planning preferences" before planning
begins. ADR-018 delivered the first half through GOAL-005, and reported the criterion as **partly met**
for exactly one reason: `study_goals.planning_preferences` was not created, so GOAL-004 could not accept
preferences without promising storage the database had not got.

Both earlier records named the same blocker and neither resolved it. ADR-013 recorded the column as an
approved target that "arrives with the planning code that uses it"; ADR-016 gave the same reason for
GOAL-004 refusing the field; ADR-018 left open "whether `planning_preferences` arrives with the planner
or before it."

Taking it now is a **deliberate departure from ADR-011's ordering rule**, which is why it needs a
record. That rule says a column waits for the code that reads it, so that no requirement-free decision
is fixed from an implementation seat. No planner exists. The countervailing argument is that FR-002's
criterion is about what a *learner can do*, not about what consumes the result — and availability was
counted as satisfying its half one change ago on precisely that basis, with ADR-018 recording as a
Neutral consequence that "nothing reads availability yet."

Five questions had to be answered, and [ADR-014](ADR-014-api-response-contract.md) had already fixed
the envelope, the pagination shape, and the error catalogue, so none of those was open.

1. **Which preferences.** "Basic planning preferences" is defined nowhere. The phrase appears in FR-002
   and in [MVP scope](../requirements/mvp.md), and [LearnFlow product agents](../ai/learnflow-agents.md)
   lists "availability slots and planning preferences" among the planner's inputs without naming one.

2. **How they are stored.** [schema.md](../database/schema.md#study_goals) approves
   `planning_preferences jsonb nullable`. The same document reserves `jsonb` for "flexible
   provider/resource payloads, not core relational concepts" and requires enumerated values to be
   validated text guarded by a `CHECK`. The approved target and the approved conventions disagree.

3. **Where they are written.** GOAL-004's catalogue entry originally promised them, and no endpoint
   exists for them. GOAL-005 set a precedent for a nested `PUT` over a group belonging to a goal.

4. **What a partial update means.** ADR-016 fixed absent-versus-null for a goal's scalar fields. A
   *group* of fields raises a question those rules do not answer: whether sending it merges into the
   stored group or replaces it.

5. **What an unset preference is.** ADR-017 and ADR-018 both drew a distinction between a value the
   learner chose and no record at all. Whether an unset preference is a null or a stored default is the
   same question again, and it decides whether the product can tell a learner's decision from its own
   guess.

## Decision

### Two preferences: a preferred session length and a topic order

`preferred_session_minutes` (15 to 480) and `topic_sequencing` (`syllabus_order` or
`prerequisites_first`).

Both were chosen on two tests: a planner cannot avoid the question, and the answer is usable against
data that already exists.

- **A planner slicing a day's `available_minutes` into `plan_items.estimated_minutes` must choose
  between one long block and several short ones**, and only the learner knows which they can sustain.
- **A roadmap must walk the curriculum in some order.** `syllabus_order` follows the stored `position`
  of subjects and topics; `prerequisites_first` follows the `prerequisite` edges in
  `topic_relationships`. Both are computable today.

**`preferred_session_minutes` is a duration, not a time of day.** It is the same kind of value as
`available_minutes`, so it does not reopen ADR-018's deliberate refusal to store clock times; nothing
here records when in a day a session falls.

**A revision share, a practice share, and a pre-examination revision buffer were considered and left
out**, under *Alternatives* below. So was a topic order that ranks by evidence: the evidence that would
produce such an order is not stored, so the choice would name a strategy nothing can execute.

### Typed nullable columns, not `planning_preferences jsonb`

Two columns on `study_goals`, each guarded by a `CHECK`: `preferred_session_minutes integer` bounded
15–480, and `topic_sequencing varchar(32)` constrained to the two documented values.

**This departs from the documented `jsonb` target**, the way ADR-018 departed from the documented
`smallint`, and for a related reason. No `CHECK` can guard a key inside a JSON document, so a
controlled value stored that way is validated only by application code — the exact situation ADR-018
removed from `day_of_week`, where "a client that assumes the wrong one silently misfiles an entire week,
and no constraint, type, or test can catch it." A misspelled key inside `jsonb` stores successfully and
reads back as absent.

It is also the consistent choice. `topic_sequencing` joins `late_registration`, `recommended_before`,
`practice_ready`, and `monday` as validated text guarded by a `CHECK`
([ADR-011](ADR-011-sqlalchemy-persistence-implementation.md)), and the stored form is the wire form,
which is the rule ADR-017 fixed.

The cost is that a third preference is a migration rather than a data change. That is accepted: an
additive nullable column is the change [migrations.md](../database/migrations.md#additive-changes-first)
prefers, and a preference the planner turns out to need is worth one migration to name properly.

### An unset preference is `NULL`, never a stored default

Both columns are nullable with **no database default**, and nothing supplies one in the application
either.

A preference nobody set must stay distinguishable from one set to the value the product would have
guessed. This is the distinction ADR-017 drew between an explicit `not_explored` and no record, and
ADR-018 drew between zero minutes and a day with no row. A planner meeting `NULL` chooses its own
default *visibly*, in code a contributor can read, rather than inheriting one a migration invented.

A learner who has answered one question and not the other is a real state, so neither field waits for
the other.

### GOAL-001 and GOAL-004 carry them; there is no new endpoint

The create and update bodies accept `planning_preferences`, and every goal response carries it. This is
what GOAL-004's catalogue entry originally promised, and what
[endpoints.md](../api/endpoints.md#goal-004-patch-apiv1study-goalsgoal_id) has been explicitly
withholding.

**A dedicated endpoint was rejected**, which is the opposite of the conclusion ADR-018 reached for
availability — deliberately. GOAL-005 exists in the catalogue and had to be implemented rather than
replaced; a preference endpoint would be an *eighth* public contract added where GOAL-004 already exists
with the right method and the right ownership rule. Availability also hangs off its own table with its
own rows; a preference is two columns on the goal, so the write that changes a goal is the write that
changes them.

A consequence worth stating: the setup screen writes preferences in the **same request** as the goal, so
unlike the profile-and-goal pair ADR-016 had to accept, there is no new partial outcome to report.

### A supplied group replaces the whole group

Sending `planning_preferences` makes it the goal's preferences: a member left out of a supplied group is
**unset**, not left at its stored value. Omitting the field entirely leaves the stored group alone. An
explicit `null` and an empty object both clear every preference.

This is GOAL-005's whole-week replace, applied to a group of columns instead of a set of rows, and for
the same reason: **a form shows every preference at once**, so a control the learner cleared has to
reach the API as a clearance. A merge would let a cleared box keep its old value, which is the failure
ADR-016 avoided for `display_name` by giving `null` a meaning absence could not express.

Because an empty group is a value distinct from no group at all, this needs **no `clear_` flag** of the
kind `target_date` requires. The asymmetry is recorded where the structure lives rather than left to be
noticed.

Saving the preferences already stored is accepted and writes nothing, the rule GOAL-005 and PRG-004
already follow.

### Nothing consumes, ranks, or scores a preference

No plan is generated, no preference is compared with another, and no preference produces a number. Both
are planning inputs, and Milestone 3's planner is what reads them — the same position availability holds
under ADR-018 and `stage_source` holds under ADR-017.

The home screen says so in the page: a saved preference is reported with the plain statement that no
plan is generated yet, so a learner cannot mistake a stored preference for one that has changed
something.

### The write goes through the existing Next.js server action, and the backend gains no CORS

Preferences are two more controls on the setup form, posting to the `"use server"` module that already
writes the profile and the goal. The browser still issues no request to the backend, so
`API_CORS_ALLOWED_ORIGINS` stays planned rather than implemented.

This inherits [ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md), ADR-016,
ADR-017, and ADR-018 rather than renegotiating them. A number box and a select have no interaction a
server round trip cannot serve, and the form works without JavaScript.

## Consequences

### Positive

- **FR-002's second acceptance criterion is met in full**, so four of its five criteria are met and one
  — receiving an initial plan — remains, waiting on Milestone 3.
  [endpoints.md](../api/endpoints.md#fr-002-acceptance-criteria) carries the count and stays
  authoritative for it.
- Every preference is a constrained column, so a value the application forgot to check is refused by the
  database rather than stored and trusted later.
- **No new endpoint**, and no new error code: `validation_error`, `not_found`, and `conflict` all
  existed. The only public change is two compatible additions to GOAL-001 and GOAL-004 and one to the
  goal response, under [versioning](../api/versioning.md#compatible-changes-within-a-major-version).
- The migration adds two nullable columns and reinterprets nothing. Every goal already stored reads back
  with no preferences set, which is true of it — the learner had no way to express one.
- The learner-planning schema area is now complete except for `study_plans` and `plan_items`, and both
  arrive with the planner that reads them.
- `scripts.set_study_goal` stays idempotent. It copies the stored preferences onto the record it writes,
  so a re-run neither discards a preference nor reports the goal as updated for leaving them alone.

### Negative

- **This creates columns before the code that reads them**, against ADR-011's ordering rule. The risk
  ADR-011 names is real: a planner may find that a session length wants a range rather than a single
  value, or that a topic order needs a third choice. Each is an additive migration, but the shape is now
  a public contract, and changing a field on GOAL-001 or GOAL-004 is breaking under
  [versioning](../api/versioning.md#breaking-changes).
- **"Basic planning preferences" is still not defined by any requirement**, so the choice of exactly
  these two is an engineering judgement recorded here rather than an approved product definition. A
  planner may want more.
- A third preference is a migration and a widened contract, where a `jsonb` column would have taken it
  as data. That is the deliberate trade for enforceable constraints.
- `study_goals` grows two columns, so a goal row now carries planning inputs beside its horizon. The
  alternative — a fourth learner-planning table for two nullable values — was rejected below.
- Replacing as a group means a client changing one preference must send both. That is the right shape
  for the form that exists and the wrong one for an inline per-preference control, which no screen has —
  the same trade ADR-018 accepted for a week.
- A preference can be saved that no plan will honour for as long as no plan exists. The page says so;
  nothing enforces it.

### Neutral

- Nothing reads a preference yet. It is written and returned, which is the position availability holds
  under ADR-018 and `stage_source` under ADR-017.
- The two preferences are never compared or combined. A learner may set one and not the other, and no
  code treats either as more important.
- No command-line tool records a preference. `scripts.set_study_goal` is untouched apart from carrying
  the stored group across.
- The setup screen gains a fieldset rather than a form, so the number of writes a learner performs is
  unchanged.

## Alternatives considered

### `planning_preferences jsonb`, as `schema.md` documents

The literal reading of the approved target. One column, and a new preference needs no migration at all.

**Not selected:** no `CHECK` can guard a key inside a JSON document, so `topic_sequencing` would be a
controlled value with nothing but application code between it and the row — the situation ADR-018
removed from `day_of_week` because "no constraint, type, or test can catch it." A misspelled key stores
successfully and reads back as absent. `schema.md` also reserves `jsonb` for provider and resource
payloads rather than core relational concepts, so following the target would contradict the conventions
in the same document.

### Typed columns, `NOT NULL` with database defaults

Every goal always has preferences, so no reader needs a null branch and no planner needs a fallback.

**Not selected:** it makes the product invent a decision and then report it back as the learner's. A
learner who never opened the form would read identically to one who chose those values, and FR-002's
"the learner can set" would be satisfied by a default nobody set. It destroys exactly the distinction
ADR-017 and ADR-018 each preserved.

### A separate `study_goal_planning_preferences` table

One row per goal, keeping `study_goals` narrow, and symmetrical with `availability_slots`.

**Not selected:** it is a fourth learner-planning table for two nullable scalars, a join on every goal
read, and a new distinction to define between "no row" and "a row whose members are null" — where the
columns themselves already express the only distinction that matters. Availability earns its table by
holding up to seven rows keyed by day; a preference group holds one of each.

### A new GOAL-006 `PUT /study-goals/{goal_id}/planning-preferences`

Symmetrical with GOAL-005, and preferences would get their own form and their own action.

**Not selected:** GOAL-004 already exists, already resolves ownership, and already promised this field
in its catalogue entry. GOAL-005 had to be implemented because it was catalogued; adding an eighth
endpoint where a catalogued one already covers the intent is the mistake ADR-018 refused when it
rejected per-slot endpoints for "replacing the catalogued GOAL-005 rather than implementing it." A
preference is also two columns on the goal row, not a child collection, so the write that changes a goal
is the write that changes them.

### Merge a supplied preference group into the stored one

`{"planning_preferences": {"topic_sequencing": "syllabus_order"}}` would change one preference and leave
the other, matching the per-field `PATCH` rule ADR-016 fixed for scalars.

**Not selected:** the form shows both controls, so a box the learner cleared would silently keep its old
value — there would be no way to express "unset this one" short of a per-member null, which is a third
rule for a two-field group. Replace is one rule, it matches GOAL-005, and clearing needs no new spelling.

### Flat preference fields on the goal body

`preferred_session_minutes` and `topic_sequencing` as top-level fields on GOAL-001 and GOAL-004,
inheriting ADR-016's absent-versus-null rule with no new semantics at all.

**Not selected:** it scatters planning inputs among `target_date` and `status`, which they have nothing
to do with, and every future preference widens the goal body again. A named group keeps them visibly one
thing on the wire and in the response, and it is what a form submits.

### A pre-examination revision buffer, and revision or practice shares

"Stop starting new topics N days before the examination window", and what share of available time goes
to revision or to practice. All three are real planner inputs, and the buffer needs only the horizon,
which exists.

**Not selected:** each is a preference *about* work the product does not model. A revision share means
nothing until revision scheduling exists — `revision_records` arrives with Milestone 3 — and a practice
share means nothing until practice does. The buffer is the closest call, and it was left out because it
is a revision decision in date clothing: what a learner does inside the buffer is revision, and no
revision rules exist to be constrained. Each is an additive nullable column when its consumer arrives.

### A topic order that ranks by evidence

`priority_focus_first`, ordering topics by where the learner most needs work.

**Not selected:** the evidence that would produce such an order is not stored — no study activity, no
quiz outcome, no external test result — so the choice would name a strategy nothing can execute, and a
learner selecting it would get syllabus order without being told. Adding a third value to the `CHECK`
is an ordinary constraint change when the evidence exists.

### Wait for the planner, as ADR-011's rule prescribes

Leave the column uncreated and FR-002's criterion partly met until Milestone 3, when the code that reads
a preference can decide its shape.

**Not selected by the project owner**, who directed that this change complete the criterion. The
argument for waiting is recorded above under *Context* and its cost under *Negative*: the shape is now a
public contract fixed before its consumer exists. The argument against waiting is that FR-002 describes
what a learner can do, availability was counted on that basis one change ago, and a learner cannot state
how they want to study at all until something stores it.

## Implementation notes

- Endpoint fields and per-endpoint error codes are in
  [api/endpoints.md](../api/endpoints.md#learner-setup-and-goal-endpoints), which stays authoritative.
  No new error code was needed.
- Migration `20260806_02_add_study_goal_planning_preferences` adds two nullable columns and two `CHECK`
  constraints to `study_goals` and alters nothing else. No index: nothing filters or orders goals by a
  preference, and [schema.md](../database/schema.md#required-indexes) lists none for this table.
- `TOPIC_SEQUENCING_CHOICES`, `MINIMUM_SESSION_MINUTES`, and `MAXIMUM_SESSION_MINUTES` live in
  `application/dto/planning_preferences.py` and are mirrored by the model's `CHECK`s, the same way
  `WEEKDAYS` and `MINUTES_IN_A_DAY` are mirrored under ADR-018.
- `PlanningPreferences` travels on `StudyGoalRecord`, because the columns live on that row. Two
  consequences were made deliberate rather than incidental: `ManageStudyGoals.update` detects a changed
  preference through the record equality check it already performs, and `SetStudyGoal` copies the stored
  group onto the record it writes so a re-run neither discards a preference nor reports a spurious
  update. `tests/unit/test_set_study_goal.py` holds both to account.
- GOAL-001 and GOAL-004 are served by `ManageStudyGoals`, so the rule deciding whether a goal belongs to
  the effective learner stays in one place. The provider in `composition/providers.py` already owns the
  transaction and needed no change.
- The frontend is a fieldset on `features/onboarding/LearnerSetupForm.tsx` with its reading in
  `submission.ts`, presentation in `features/onboarding/preferences.ts`, and a read-only
  `features/home/PlanningPreferences.tsx`. No new server action: `saveLearnerSetup` already writes the
  goal, and the preferences ride on that request.
- **The PostgreSQL integration tests cannot be run on the authoring workstation**, which has neither
  PostgreSQL nor Docker, so they skip there with no `TEST_DATABASE_URL`. CI ran them, and **they found a
  defect this record's first push contained**: the downgrade named its two `CHECK` constraints in full,
  and Alembic interpolates a supplied name through the `ck` convention on drops as well as creates, so
  it rendered `ck_study_goals_ck_study_goals_topic_sequencing_is_known` and failed. Because the
  integration fixture downgrades in teardown, one broken statement surfaced as errors across the whole
  database job rather than as a single failure.

  The fix drops the two columns and names neither constraint: PostgreSQL removes a check that depends on
  a dropped column, which also keeps the downgrade clear of the convention entirely.
  `tests/unit/test_migration_sql.py` now renders both directions of the chain offline and asserts that
  no constraint name repeats its convention prefix and none overruns PostgreSQL's identifier limit —
  a guard that needs no database and fails on the original mistake.
  [migrations.md](../database/migrations.md#commands) records the trap and the habit that avoids it.
- **Verified against the production standalone server with a contract-shaped stub API**, as ADR-015
  through ADR-018 were. Twenty-seven checks passed: a no-JavaScript multipart submission of the setup
  form created a goal carrying `{"preferred_session_minutes": 90, "topic_sequencing":
  "prerequisites_first"}` with no `learner_id`; both preferences read back on `/setup` — the number box
  filled, the order the selected option — and on `/`, beside the statement that no plan acts on them;
  a second submission clearing one box sent the whole group with that member `null`, which unset it and
  left the other, so the home screen dropped one row and kept the other; a submission clearing both
  sent a group of two nulls, after which the home screen reported none saved and the form returned to an
  empty box and a selected *No preference*; a session length of 9000 was refused with nothing stored;
  the rendered panel carried no total and no score; and neither the API address nor `API_BASE_URL`
  appeared in the HTML of `/`, `/setup`, or `/curriculum`, nor in any of the eleven client scripts they
  load.
- **The form always sends a complete group, so it never emits a literal `{}` or `null`.** A cleared
  control travels as an explicit `null` member, which reaches the same stored state. The two shorter
  spellings are contract affordances for other clients rather than paths this UI takes, and they are
  covered where they apply — `tests/api/test_learner_onboarding.py` asserts that `null` and `{}` each
  clear every preference and that an omitted field leaves the group alone, against the real application
  factory.
- **The documentation set was reviewed by hand rather than by the `documentation-reviewer` agent**,
  which could not be run — four attempts ended in an upstream API failure. The manual sweep covered what
  that agent checks: stale claims that preferences are not accepted or that the column is not created,
  the FR-002 count against
  [endpoints.md](../api/endpoints.md#fr-002-acceptance-criteria) as the authoritative source,
  terminology consistency including the avoid-list, and link resolution alongside
  `scripts/validate_docs.py`. It found one defect, since fixed: test fixtures used `weakest_first` as an
  invalid `topic_sequencing`, and *weak* is on the avoid list. The project owner accepted the manual
  sweep as sufficient for this change.
- Open and deliberately not settled here: which further preferences a planner turns out to need, whether
  a session length ever becomes a range, and how a planner should behave when a preference and a week
  cannot both be honoured.
- Recorded as DEC-031 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](ADR-011-sqlalchemy-persistence-implementation.md) — the ordering rule this record departs from, and the validated-text rule it follows
- [ADR-013: Model an examination period as a published window of reference data](ADR-013-examination-schedule-and-study-goal.md) — the record that held `planning_preferences` back
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the envelope these contracts answer in
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology the preference controls inherit
- [ADR-016: Fix the learner setup API contracts](ADR-016-learner-onboarding-api-contracts.md) — the GOAL-004 contract this record extends, and the absent-versus-null rule it builds on
- [ADR-017: Record manual topic progress as a learner-owned stage](ADR-017-topic-progress-api-and-schema.md) — the stored-form rule and the absent-versus-explicit distinction this record reuses
- [ADR-018: Store weekly availability as named days replaced a week at a time](ADR-018-weekly-availability-slots.md) — the other half of FR-002's criterion, the replace-the-group precedent, and the documented-target departure this one repeats
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](ADR-020-initial-study-plan-generation.md) — the planner that reads these preferences, and the risk this record recorded that did not materialise
- [API conventions](../api/conventions.md) — the envelope, the error codes, and the `snake_case` rule
- [API endpoint catalog](../api/endpoints.md) — the contract this record decides
- [API versioning](../api/versioning.md) — what makes a change to it breaking
- [Database schema](../database/schema.md) — the approved target, and the column shape this record changes
- [Database migrations](../database/migrations.md) — the migration this record introduces
- [Domain model](../domain/domain-model.md) — planning preferences as a planning input
- [Domain entities](../domain/entities.md) — the study goal that owns them
- [Terminology](../domain/terminology.md) — *planning preference*, *session length*, and *topic order*
- [Functional requirements](../requirements/functional.md) — FR-002, and the criterion this record completes
- [Repository and folder structure](../development/folder-structure.md) — where the new modules live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 2 item this completes
- [Architecture decision register](../architecture/decisions.md) — DEC-031
