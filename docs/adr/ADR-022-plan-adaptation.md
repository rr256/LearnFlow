---
title: "ADR-022: Adapt a Study Plan by Rebuilding It Around What Happened"
status: proposed
owner: architecture-and-data
last_updated: 2026-08-09
related:
  - ../00-project-context.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-018-weekly-availability-slots.md
  - ADR-020-initial-study-plan-generation.md
  - ADR-021-plan-item-completion.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../api/versioning.md
  - ../database/schema.md
  - ../domain/domain-model.md
  - ../domain/entities.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../deployment/docker.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../architecture/decisions.md
---

# ADR-022: Adapt a Study Plan by Rebuilding It Around What Happened

## Status

Proposed — 2026-08-09.

This delivers [FR-004](../requirements/functional.md#fr-004-plan-adaptation)'s **second** acceptance
criterion in full — "when work is missed or availability changes, the learner can request an updated
plan" — and takes the **first** further than [ADR-021](ADR-021-plan-item-completion.md) did:
completing and postponing are both now reachable, and only *skipping* remains unbuilt. The **third** criterion, highlighting trade-offs when time is insufficient, is **not** delivered;
see *Consequences*.

## Context

Three records have now built toward this one and each stopped at the same wall.

[ADR-020](ADR-020-initial-study-plan-generation.md) generated the first plan and recorded, under
*Negative*, exactly what was missing: "**A weekly plan goes stale.** It covers seven days from the day
it was generated, and nothing re-plans it: a learner who misses a week must generate again, which is
FR-004's work arriving later."

[ADR-021](ADR-021-plan-item-completion.md) let a learner mark an item completed and was blunt about
the consequence: "**A completion survives a re-plan without meaning anything.** Generating again
supersedes the plan the completed item belongs to, and the new plan's items all start `planned` — so
a learner who completed Monday and then rebuilt their plan sees that work offered again." It also
refused `skipped` and `postponed` outright, because "postponing work raises the question of what it
moves *to*, which is the re-planning PLN-005 does not yet do."

So today a learner who has done half their week and then regenerates is offered the whole week again.
Their completions are stored, visible, and inert. That is the gap this closes.

Seven questions had to be answered, and the project owner decided each of them.
[ADR-014](ADR-014-api-response-contract.md) had already fixed the envelope and the error catalogue, so
none of that was open.

1. **What triggers adaptation.** FR-004 says "the learner can request an updated plan"; nothing says
   whether anything else may.
2. **Whether adaptation supersedes or edits in place.** ADR-020 chose superseding for generation and
   [schema.md](../database/schema.md) requires plan history to stay explainable.
3. **What completed work does to the new plan** — the question ADR-021 left open by name.
4. **What happens to work whose day passed with the task undone**, and whether `postponed` is finally
   written.
5. **Which plan types adaptation produces.** `monthly` and `daily` remain constrained and unwritten.
6. **Which path and which topology.** PLN-005 has been catalogued as
   `POST /api/v1/study-plans/{plan_id}/adapt` since the documentation foundation.
7. **Whether this needs an ADR**, given the endpoint was catalogued.

### One finding that shaped the answers

**Everything adaptation needs is already stored.** A topic the learner has completed is derivable by
joining `plan_items.status = 'completed'` to the goal's plans; overdue work is derivable from
`scheduled_for < today` with the item still `planned`. **This change therefore adds no column, no
table, and no migration**, and no existing record is reinterpreted — which is what let it be built
without touching a learner's stored plans at all.

## Decision

### The learner asks; nothing adapts on its own

Adaptation happens when the learner presses a control, and at no other time. Completing an item
re-plans nothing. Saving a new study week re-plans nothing. There is no scheduler, no background job,
and no side effect on another endpoint.

This is FR-004's own wording, and it keeps ADR-021's accepted promise that "only the named item
moves". It also keeps the feature deterministic in the way that matters to a learner: the plan
changes at a moment they chose, so a list cannot rearrange itself under a hand that is ticking it.

**Adapting on a changed study week was rejected**, under *Alternatives*: a settings save that silently
rewrites the plan is a surprise, and GOAL-005 currently promises to touch nothing but availability.

### Adaptation supersedes, exactly as generation does

The goal's `active` plans become `superseded` and a new pair is written. One lifecycle serves both
endpoints; nothing is deleted; the learner's plan history stays readable, which is what
[schema.md](../database/schema.md#referential-integrity-and-lifecycle-notes) asks of plans and what
ADR-020 decided.

**Editing the active plan in place was rejected.** It would destroy the record of what was originally
planned — the thing superseding exists to preserve — and leave `generation_reason` describing a plan
that no longer matched it.

### A completed topic is not planned again

A topic with a `completed` item **anywhere on this goal**, including on a plan superseded months ago,
is left out of the new plan. Superseding a plan does not un-complete the work done under it.

The exclusion happens **before** the ordering and placement rules run, not as a filter afterwards. An
adapted plan is therefore a real plan over the topics that remain — the plan the learner would have
been generated had those topics never been in the curriculum — rather than a generated plan with
holes in it.

**Carrying completed items forward into the new plan was rejected**: it would duplicate completion
records across plans, make `item_count` mean two different things, and blur ADR-020's guarantee that a
superseded plan reads exactly as it was written.

### Overdue work is marked `postponed`, and its topic is planned again

An item whose day has passed with the work undone is written `postponed` **on the plan being set
aside**, and its topic is re-placed on the plan that replaces it.

This is the answer to the question ADR-021 could not answer — postponed *to where?* — because the new
plan is where. It is the first code to write the status, which has passed the `CHECK` unwritten since
`20260806_03`.

The history then says what happened to every line: `completed`, `postponed`, or `planned` and never
due. Leaving them `planned` would make a missed day indistinguishable from one that was never
reached.

**What makes an item overdue is a pure domain rule**, `select_overdue` in
`backend/app/domain/study_planning.py`, so three boundaries are decided rather than discovered:

- **An item dated today is not overdue.** The day has not finished; adapting in the morning must not
  declare it lost.
- **An undated roadmap item is never overdue.** It cannot be late for a day it never named.
- **Completed work is never overdue**, however late it was completed.

`skipped` stays unwritten. Nothing yet lets a learner abandon a topic outright, and inventing that
alongside adaptation would be two features in one change.

### Roadmap and weekly, by the same rules as generation

Adaptation writes the pair PLN-001 writes. `monthly` and `daily` remain constrained and unwritten, as
ADR-020 left them; delivering them inside a change about adaptation would settle what they *are* as a
side effect.

The ordering rule, the session placement, the week, the horizon, the session length, and the stage
sentences are **identical** to generation's — literally the same code path, `_compose`, with one
parameter differing. The only difference between a generated and an adapted plan is which topics went
in.

### A goal-scoped path, departing from the catalogue

`POST /api/v1/study-goals/{study_goal_id}/adapt`. The catalogued
`POST /api/v1/study-plans/{plan_id}/adapt` is **not** used, and
[endpoints.md](../api/endpoints.md#planning-endpoints) is amended rather than filled in.

Adaptation supersedes and rewrites every active plan of a goal — the roadmap and the week together.
A path naming one plan would misdescribe what moves, and would raise the unanswerable question of what
happens when the learner names the roadmap rather than the week. The goal is the thing being adapted.

**The endpoint takes no request body.** Everything it acts on is already stored, so no caller can
adapt toward a preference the learner never set — the guarantee PLN-001 also keeps.

**A goal with no active plan is refused with `409`.** Adaptation rebuilds a plan around what happened
to it; with no plan there is no "what happened", and building a first one is PLN-001's work.

### The write goes through a Next.js server action, and the backend gains no CORS

The `/plan` control posts to a `"use server"` module, which calls the API with the server-side
`API_BASE_URL` and revalidates `/plan`. The browser issues no request to the backend, so
`API_CORS_ALLOWED_ORIGINS` stays planned. This inherits
[ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md) rather than renegotiating it,
and the form works without JavaScript.

The control appears **only when a plan exists**, matching the `409` the backend returns, and its hint
says what adapting will do — what is dropped, what is carried forward, and that the old plan is
kept — before it is pressed.

## Consequences

### Positive

- **A learner's completions finally mean something.** The inert-completion problem ADR-021 recorded
  under *Negative* is discharged: finishing work shortens the plan.
- **`postponed` has a meaning and a writer**, and the question ADR-021 could not answer is answered.
- **No migration, no column, no table.** Every input was already stored, so no learner record is
  reinterpreted and no existing plan is touched.
- **An adapted plan is explainable in the same terms as a generated one**, and says the two extra
  things only an adaptation can: what is not planned again, and what was carried forward.
- **Generation and adaptation cannot drift.** They share `_compose`, so a change to the ordering or
  the placement rule reaches both or neither.
- No new error code was needed: `not_found` and `conflict` both existed.
- **The domain layer gains its third rule**, and it is pure: what counts as behind is testable without
  a clock.

### Negative

- **A fifth endpoint is public contract**, and it **departs from the catalogued path**. Changing it
  again is breaking under [versioning](../api/versioning.md#breaking-changes).
- **FR-004's third criterion is still unmet.** Nothing highlights that the learner's week cannot reach
  their horizon. An adapted plan says how much is left, not whether it fits — the same gap ADR-020
  recorded, narrowed but not closed.
- **Adaptation accumulates plans faster than generation did.** Every adaptation writes two more rows
  and supersedes two; a learner adapting weekly accumulates them. Nothing prunes them, which
  superseding deliberately causes.
- **A topic completed once is never planned again on that goal**, even if the learner would benefit
  from revisiting it. Revision is Milestone 3 work that does not exist, so today the only way back to
  a completed topic is to return its item to `planned` through PLN-004.
- **`skipped` remains unwritten**, so a learner who wants to abandon a topic still cannot say so.
- **The counts are learner-facing prose in a stored sentence**, as ADR-020's stage labels are. A
  reworded count leaves older plans carrying the older wording.

### Neutral

- Nothing here totals a day, a week, or a plan, and nothing ranks or scores a topic or a learner. The
  two counts describe the plan's coverage, which is the line ADR-020 drew when it let a plan state
  "60 topics".
- `monthly` and `daily` are still constrained and unwritten, as `practice`, `revise`, and
  `review_mistakes` are.
- No AI provider is involved. The same inputs produce the same adapted plan.
- No command-line tool adapts a plan.

## Alternatives considered

### Adapt automatically when a study week is saved

GOAL-005 would trigger a re-plan, so a changed week takes effect at once.

**Not selected:** a settings save that silently rewrites the plan is a surprise, and GOAL-005 promises
to touch nothing but availability. A learner who changes their week and wants it applied can press the
control — which is one action, visible, and reversible in the sense that the old plan is kept.

### Adapt automatically after every completion

The plan stays current with no action.

**Not selected:** it contradicts ADR-021's accepted decision that "only the named item moves" and
"nothing is re-planned", and it would rearrange a list under a learner who is ticking it.

### Edit the active plan in place

Re-date the pending items of the existing weekly plan; leave completed ones alone.

**Not selected:** no row accumulation, and a bookmarked plan id would stay valid — but it destroys the
record of what was originally planned, which is precisely what superseding exists to preserve, and it
would leave `generation_reason` describing a plan that no longer matches it.

### Carry completed items into the new plan

Copy them across with their `completed_at`, so one plan shows the whole picture.

**Not selected:** it duplicates completion records across plans, makes `item_count` ambiguous, and
weakens the guarantee that a superseded plan reads as written. The completed work is not hidden — the
superseded plan still holds it, and the new plan's reason says how many topics are not repeated.

### Leave overdue items `planned` on the superseded plan

The strictest reading of "reads exactly as it was written".

**Not selected:** nothing would then distinguish a missed item from one never due, and `postponed`
would stay unwritten with no obvious future home. The superseded plan's *reasons* and *content* are
still never rewritten; only the status of work the learner did not do moves, which is a statement
about what happened rather than about what was planned.

### Use the catalogued `POST /study-plans/{plan_id}/adapt`

No catalogue amendment, and the path reviewers expect.

**Not selected:** adaptation supersedes both of a goal's active plans. A path naming one would
misdescribe the effect and raise an unanswerable question about naming the roadmap versus the week.

### Extend PLN-001 with a flag

`POST /study-plans/generate` with something like `adapt: true`.

**Not selected:** it puts two behaviours behind one endpoint whose current guarantee is that nothing a
client sends changes what the plan is built from — a property ADR-020 chose deliberately.

## Implementation notes

- Endpoint fields and per-endpoint error codes are in
  [api/endpoints.md](../api/endpoints.md#pln-005-post-apiv1study-goalsstudy_goal_idadapt), which stays
  authoritative.
- **No migration.** `plan_items.status` accepts `postponed` through the `CHECK` created by
  `20260806_03`; this is the first code to write it.
- `select_overdue` and `DatedItem` are in `backend/app/domain/study_planning.py`, the third rule in the
  domain layer. `POSTPONED` joins the constants in `application/dto/study_plan.py`.
- `ManageStudyPlans.adapt` serves the endpoint. `_compose` and `_write_pair` were extracted from
  `generate` so both paths share one route through the reads and the two pure rules; `generate`'s
  behaviour is unchanged, which its existing tests establish.
- `StudyPlanRepository` gained `list_completed_topic_ids`, unpaged: it answers a membership question
  once per adaptation, so there is nothing to order or window.
- The route lives on a second `APIRouter` in `presentation/api/routes/study_plans.py` with the
  `/study-goals` prefix — the operation is planning work served by `ManageStudyPlans`, but its path is
  goal-scoped.
- The frontend is `features/planner/AdaptPlanForm.tsx` with `adaptPlan` in the existing `actions.ts`
  and its state shape in `submission.ts`, because a `"use server"` module may export only async
  functions, which `frontend/tests/server-actions.test.ts` enforces.
- **The PostgreSQL integration tests were run locally**, for the first time in this repository's
  history: Docker Compose now works (see
  [docker.md](../deployment/docker.md#first-local-run-2026-08-08)), so a disposable `learnflow_test`
  database was created beside the development one and the whole suite ran green — **923 passed, 0
  skipped**. The learner's `learnflow` database was not touched.
- Open and deliberately not settled here: when `skipped` arrives and what it means for adaptation;
  whether a completed topic should ever be planned again before revision exists; whether superseded
  plans are ever pruned; and how a plan should report that a week cannot reach its horizon, which is
  FR-004's remaining criterion.
- Recorded as DEC-034 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](ADR-011-sqlalchemy-persistence-implementation.md) — the validated-text rule the `postponed` `CHECK` follows
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the envelope and error codes this contract answers in
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology this control inherits
- [ADR-018: Store weekly availability as named days replaced a week at a time](ADR-018-weekly-availability-slots.md) — the week an adapted plan is placed into
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](ADR-020-initial-study-plan-generation.md) — the plan this rebuilds, the rules it reuses, and the stale-week problem it names
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](ADR-021-plan-item-completion.md) — the completions this consumes, and the `postponed` question it left open
- [API conventions](../api/conventions.md) — the envelope, the error codes, and the `snake_case` rule
- [API endpoint catalog](../api/endpoints.md) — the contract this record decides, and the catalogued path it departs from
- [API versioning](../api/versioning.md) — what makes a change to it breaking
- [Database schema](../database/schema.md) — `plan_items.status`, and the first write of `postponed`
- [Domain model](../domain/domain-model.md) — rule 4, which adaptation does not breach
- [Domain entities](../domain/entities.md) — the study plan and plan item this rebuilds
- [Terminology](../domain/terminology.md) — *study plan*, *plan item*, and the refusal to rank
- [Functional requirements](../requirements/functional.md) — FR-004's three criteria, two now met
- [Repository and folder structure](../development/folder-structure.md) — where the domain rule and the planner feature live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 3 items this closes
- [Architecture decision register](../architecture/decisions.md) — DEC-034
