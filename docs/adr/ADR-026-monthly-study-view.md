---
title: "ADR-026: Show the Month as a Reading of the Roadmap and the Week, Not a Monthly Plan"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-13
related:
  - ../00-project-context.md
  - ADR-013-examination-schedule-and-study-goal.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-016-learner-onboarding-api-contracts.md
  - ADR-020-initial-study-plan-generation.md
  - ADR-021-plan-item-completion.md
  - ADR-022-plan-adaptation.md
  - ADR-023-daily-study-view.md
  - ADR-024-plan-item-skipping.md
  - ADR-025-learner-postponement.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../database/schema.md
  - ../domain/domain-model.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../development/coding-standards.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../architecture/decisions.md
---

# ADR-026: Show the Month as a Reading of the Roadmap and the Week, Not a Monthly Plan

## Status

Accepted — 2026-08-13. Proposed 2026-08-13.

Accepted once the decision below was verified rather than merely argued. **Nothing in the decision
changed on acceptance**, and nothing is recorded here as unverified. The whole canonical check set is
green — the backend suite with warnings as errors (**752 passed**), Ruff lint and format, the frontend
lint, type check, **458 tests**, and production build, the `scripts/` checks, and the documentation
validator — and the **PostgreSQL integration tests were run locally** against the disposable
`learnflow_test` database (**227 passed**), with the development `learnflow` database untouched and
checked afterwards to confirm it. The **scriptless standalone-frontend run was performed**; see
[Implementation notes](#implementation-notes) for what it demonstrated.

This completes [FR-003](../requirements/functional.md#fr-003-study-timeline-and-plan)'s second
acceptance criterion — "the learner can view monthly, weekly, and daily recommendations" — by
delivering the **monthly** half, which [ADR-023](ADR-023-daily-study-view.md) left as the one part of
it unbuilt. It adds **no endpoint, no column, no table, and no migration**.

It answers the question ADR-023 listed first among the things it deliberately did not settle:
**"whether a monthly view is a reading or a plan."** The answer is a reading, for the reasons ADR-023
gave about a daily one.

A `monthly` `study_plans.plan_type` stays constrained and unwritten, as
[ADR-020](ADR-020-initial-study-plan-generation.md) left it. **What a `monthly` plan would *contain*
remains undecided**, exactly as what a `daily` plan contains does.

## Context

A learner has three ways to read their plan and a gap between them. `/plan` shows the whole roadmap —
every trackable topic across the horizon, in order, undated — and the week beneath it. `/plan/today`
shows one day. Neither answers *where am I in all this*: the roadmap is too long to locate yourself
in, and a day is too short to plan around.

That gap is a month. It is also the only part of FR-003's second criterion still unmet, and the last
planning item Milestone 3 holds apart from FR-004's third criterion and revision.

Six questions had to be answered, and the project owner decided each of them.
[ADR-014](ADR-014-api-response-contract.md) had already fixed the envelope and the error catalogue, so
none of that was open.

1. **Whether this is a `monthly` plan**, generated and stored, or a reading of what exists.
2. **What a month is, and who decides which one the learner is in.**
3. **Whether work the learner has completed, skipped, or postponed appears, and how.**
4. **Where the screen lives, and how a learner reaches it.**
5. **Whether the existing reads suffice.**
6. **Whether this needs an ADR.**

### One finding that shaped every answer

**A weekly plan dates seven days, and nothing else in a plan is dated at all.**

That is the constraint the whole of this record works within. `study_plans` holds two active rows per
goal: a `roadmap`, whose items carry `scheduled_for = null` by decision, and a `weekly` plan covering
the seven days from generation. So the dated work available to *any* view of a calendar month is at
most one week of it, and often none — a learner who generated a plan on the 27th sees four days in
this month and three in the next.

A month view therefore cannot be a fuller version of the week. It has to be honest about a month that
is mostly undated, or it has to invent dates. **Inventing them is what this record refuses**, and the
refusal is the decision below.

## Decision

### The monthly study view reads the roadmap and the week; it is not a `monthly` plan

A *monthly study view* is a **reading** of the goal's two active plans, filtered and grouped to one
calendar month. No `study_plans` row of type `monthly` is written, none is read, and the `CHECK` that
permits the value stays exactly as `20260806_03` created it.

This is ADR-023's decision applied a second time, and for the same reason it gave: a future
contributor meeting a screen called *month* will reasonably assume the `monthly` plan type behind it,
and there is none. What a `monthly` plan *is* — whether it re-slices a month's capacity, whether
generating one supersedes the week, whether its items duplicate the week's — remains undecided, and
settling it as a side effect of adding a screen is what ADR-020 refused when it declined to deliver
all four plan types at once.

**Generating a `monthly` plan record was rejected**, under *Alternatives*.

### The frontend does not decide how much of a roadmap a month holds

The view shows the month's **dated** days from the weekly plan, and then the roadmap topics the week
has not dated, **openly undated**, in the order the roadmap chose. It does not spread those topics
across the month's remaining days.

**This is the decision the finding above forces, and it is the one most likely to be argued with.** A
month with four dated days and twenty-six empty ones looks like a screen that has not finished. The
alternative — projecting the learner's saved study week across the rest of the month and placing the
roadmap's next topics onto those days — would fill it, and would be wrong in a way no learner could
see: those dates would exist in no stored record, would not survive a reload against a changed
availability, and would disagree with the plan the moment the learner adapted.

Placing sessions on days **is** planning. It is `schedule_sessions` in
`backend/app/domain/study_planning.py`, it is deterministic and stored, and
[coding-standards.md](../development/coding-standards.md#ui-responsibilities) reserves it for the
backend: "keep planning, progress calculation, and curriculum rules in the backend." A view that
placed work would be a second planner with no tests, no reasons, and no persistence.

So the screen states the shortfall instead — that the plan dates work as far as its `period_end`, and
that updating the plan is what gives the rest of the month days. That is the same honesty ADR-020
required of the plan itself when it made a plan say that `prerequisites_first` had changed nothing.

### The month is the learner's own, resolved from `learners.timezone`

The Next.js server reads LRN-001, converts the current instant into the learner's zone, and takes the
month from it. A zone that cannot be read falls back to UTC — the same fallback `_today_for` applies
in the backend and `learnerToday` applies on `/plan/today`.

`learnerMonth` is derived from `learnerToday` rather than resolving the instant again, so there is
**one** conversion to keep correct and one fallback to keep in step with the backend's. A month
boundary is a day boundary that matters for a whole month rather than a whole day: a learner in
`Asia/Kolkata` opening this screen at half past eleven on 31 August must not be shown September.

**Only the learner's current month is shown.** Browsing to an arbitrary month was rejected below.

Month boundaries are computed from the month's own numbers rather than through a `Date`, so no parsing
rule or host timezone can move one, and the leap-year rule is the full Gregorian one. A February
boundary wrong once a century is still wrong.

### A settled item keeps its place, marked in words

An item the learner has **completed**, **skipped**, or **postponed** appears on the day the plan gave
it, marked in words — *Marked completed*, *Marked skipped*, *Marked postponed* — exactly as it does on
`/plan`'s two panels and in the daily study view.

Hiding finished work would leave the month looking undone, and hiding a skip or a postponement would
hide a decision the learner may want to take back. The mark is carried in text and not by colour
alone, as the other panels carry theirs.

**Nothing is counted.** No completion count, no percentage, no "12 of 60 this month", no streak — the
line [terminology](../domain/terminology.md#plan-coverage-counts-are-not-learner-scores) draws, and
which every planner screen has held.

### The screen is read-only

`/plan/month` offers **no status control, no generate control, and no adapt control**. It writes
nothing at all.

**This is where the record departs from ADR-023**, which listed as a positive consequence that "a
completed item behaves identically on all three screens" because the daily view reuses
`PlanItemStatusControl`. It does not behave identically on a fourth. The departure is deliberate and
its cost is recorded under *Negative*.

The reason is what the two screens are for. A day is where a learner works — they open `/plan/today`
with the intention of ticking things off, and the control belongs under their hand. A month is where
they look: at where the dated week sits, at what the roadmap holds next, and at how far off the
horizon is. Putting three write controls beside every item of a month-long list would put sixty
decisions on a screen opened to get one's bearings, and would make a fourth surface that writes plan
item statuses — each needing its own confirmation copy, its own `409` handling for a superseded plan,
and its own place in every future change to the control.

The screen names where marking happens and links to it, which is the pattern ADR-023 used for
adaptation: a screen that does not perform an action still says who does and where.

### A new route, `/plan/month`; nothing moves off `/plan` or `/plan/today`

The monthly study view is `app/plan/month/page.tsx`. `/plan` keeps the roadmap, the week, and the two
controls that rebuild a plan; `/plan/today` keeps the day and its three controls. Each gains a link,
and so does the home screen.

Nesting under `/plan` says in the address what the screen is — a reading of the plan — for the reason
ADR-023 nested `/plan/today`. A top-level `/month` would be shorter and would lose that.

**Neither generating nor adapting appears on this screen**, for the reason ADR-023 gave about the
daily view: a control that rebuilds the plan does not belong beside a list a learner is reading.

### No new endpoint

The screen reads LRN-001, GOAL-002, PLN-002, and PLN-003 — every one an existing contract, and the
same four the daily study view reads. **No sixth planning endpoint is added**, and nothing about the
five changes: no field, no status code, no path. It writes through none of them.

The reads go through the same server-side API client every view uses. The browser issues no request to
the backend, so `API_CORS_ALLOWED_ORIGINS` stays planned rather than implemented. This inherits
[ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md) through ADR-025 rather than
renegotiating them.

## Consequences

### Positive

- **FR-003's second acceptance criterion is met in full**, for the first time. Monthly, weekly, and
  daily recommendations are all viewable, and the monthly half was its last gap.
- **A learner can locate themselves.** The screen answers *where am I in this plan* — which the
  roadmap is too long to answer and a day too short — without adding a plan to keep in step.
- **No endpoint, no column, no table, no migration.** Nothing stored is reinterpreted and no public
  contract changes, so this change is reversible by deleting a route.
- **The `monthly` plan type stays undecided rather than decided by accident**, and this record says so
  where a contributor will find it before writing one.
- **The month's honesty is structural.** A month that is mostly undated says so and says what would
  date it, rather than being filled with dates no record holds.
- **No AI provider is involved, and no configuration variable is read.** The same plans and the same
  instant produce the same month.

### Negative

- **A plan item does not behave identically on all four screens.** ADR-023 bought that property by
  reusing `PlanItemStatusControl` in the daily view; this record spends it. A learner who sees an item
  on the month screen and wants to mark it must go to `/plan/today` or `/plan`. The screen says so,
  but it is one more thing to say.
- **The screen is mostly empty for most months.** A weekly plan dates seven days, so a learner opening
  a month usually sees one week of dates and a list of undated topics. That is the true state of their
  plan, and this record chose to show it rather than disguise it — but a screen whose honest state is
  sparse is a screen some learners will read as broken.
- **A fifth learner-facing route** is another surface that must keep its loading, empty, error, and
  success states in step with the contract behind it.
- **Only the current month is reachable.** A learner cannot look at next month, which for a six-month
  horizon is most of the plan. Nothing dated lives there today, so the screen would be empty but for
  the roadmap — but the limitation becomes real the moment anything dates further ahead.
- **A third place now derives a date from `learners.timezone`.** The backend's `_today_for`,
  `learnerToday`, and now `learnerMonth` must agree. The third is derived from the second rather than
  written again, which is the most a frontend that cannot import from the backend can do.
- **The month's own arithmetic is now frontend code.** Days-in-month and the Gregorian leap rule are
  small, exhaustively tested, and dependency-free, but they are calendar rules living outside the
  domain layer that owns the plan's other rules.

### Neutral

- Nothing here totals, counts, ranks, or scores. No monthly completion count, no percentage, no
  streak.
- `monthly` and `daily` remain constrained and unwritten `plan_type` values, as do `practice`,
  `revise`, and `review_mistakes` for `action_type`. Every value of `plan_items.status` stays written
  exactly as ADR-025 left it.
- The backend is untouched by this change: no route, no use case, no DTO, no domain rule, no model,
  no migration.
- The domain layer still holds one module, and `select_overdue` is neither read nor mirrored here —
  this screen makes no claim about what is overdue, which is why it needs no fourth copy of that rule.
- FR-004's third criterion — saying whether the learner's week can reach their horizon — is still not
  delivered. This screen shows the horizon beside the month without judging whether it is reachable.

## Alternatives considered

### Generate a `monthly` plan record

Write a `study_plans` row of type `monthly` for each month, with its own items, its own
`generation_reason`, and its own supersede lifecycle, alongside the roadmap and the week.

**Not selected:** it settles what a monthly plan *is* as a side effect of adding a screen, which is
the trade ADR-020 refused when it declined all four plan types at once and ADR-023 refused again for
`daily`. It would also raise every question a dated month raises — whether its items duplicate the
week's, what `item_count` then means, whether completing a week item completes the month's copy, and
what happens to a month when the learner adapts mid-way — none of which this change needs to answer to
show a learner their month. If a `monthly` plan is later wanted, that is the change that should
introduce it, with the decision it carries.

### Project the saved study week across the month and place the roadmap onto it

Read the goal's `availability_slots`, repeat that week across the month's remaining days, and lay the
roadmap's undated topics onto them in order. The month fills up and looks like a plan.

**Not selected**, and this is the largest of the alternatives rather than a variant. It is planning
performed in the browser tier: it duplicates `schedule_sessions` without its tests, its reasons, or
its determinism guarantees, and it produces dates that exist in no stored record. Two learners with
identical plans would see the same dates from this view and different ones from any adaptation, and
nothing would reconcile them. It would also make the screen's correctness depend on the frontend
agreeing with a domain rule it cannot import — the duplication ADR-023 recorded as a cost for one
boolean, taken up again for the whole placement rule.

### Show the whole roadmap on the month screen

Drop the distinction between dated and undated work and list all sixty topics under the month.

**Not selected:** that is `/plan`'s roadmap panel, at a different address. The month screen would add
nothing except a heading claiming the topics belonged to a month nothing had placed them in — the
precise misstatement this record's central decision avoids.

### Let the learner browse to any month

`/plan/month/2026-09`, or previous and next links.

**Not selected** for this change: nothing is dated beyond the current week, so every other month would
show the same undated roadmap tail under a different heading, and the route would carry a parameter
with its own validation, its own `404`, and its own empty states for no gain the learner can use
today. It becomes worth building when something dates work further ahead — a `monthly` plan, or a
horizon-length dated plan — and it is a route change rather than a contract change when it does.

### Carry the status controls, as the daily view does

Reuse `PlanItemStatusControl` on the month screen, so an item behaves the same everywhere.

**Not selected:** see the decision above. It would put sixty items' worth of write controls on a
screen a learner opens to get their bearings, and make a fourth surface that writes plan-item statuses
— each needing its own confirmation copy, its own `409` path, and its own place in every future change
to the control. The consistency it buys is real and is recorded as this record's chief cost.

### A sixth endpoint returning the month's work

`GET /api/v1/study-plans/month`, computing the learner's month with `_today_for` and the grouping in
the backend.

**Not selected:** the objection ADR-023 raised against the same shape for a day. It is a public
contract that is breaking to change afterwards
([versioning](../api/versioning.md#breaking-changes)), for a screen that adds no capability the four
existing reads cannot serve, and the rule it would centralise decides a heading rather than a stored
value.

## Implementation notes

- **No backend file changes.** The screen consumes LRN-001, GOAL-002, PLN-002, and PLN-003 exactly as
  catalogued in [api/endpoints.md](../api/endpoints.md#planning-endpoints), which stays authoritative
  for their fields and error codes.
- The route is `frontend/app/plan/month/page.tsx`, `force-dynamic` for the reason `/plan/today` is: a
  page about a calendar period would be wrong from the first month boundary after a build. It declares
  its own `Suspense` boundary inside `page.tsx` rather than a `loading.tsx` segment file, for the
  reason [folder-structure.md](../development/folder-structure.md#frontendapp) records.
- `frontend/features/planner/month.ts` holds `learnerMonth`, `monthBounds`, `monthLabel`,
  `isWithinMonth`, `selectMonthlyWork`, and `datedWorkEndsInsideMonth` — plain functions taking the
  instant as an argument, so they are tested at fixed moments across zones without a running server.
  `learnerMonth` delegates to `today.ts`'s `learnerToday` rather than resolving the instant again.
- `frontend/features/planner/MonthlyPlanView.tsx` renders both panels and reuses `describeAction`,
  `describeEstimate`, `describeSettledStatus`, and `itemClassName` from `plan.ts`. It does **not**
  reuse `PlanItemStatusControl`, by the decision above. `PlanWeek.tsx`, `StudyRoadmap.tsx`, and
  `DailyStudyView.tsx` are untouched: extracting a shared item component from four panels is a
  refactor, and this is a feature change — the same call ADR-023, ADR-024, and ADR-025 each made.
- Covered by `frontend/tests/monthly-plan-selection.test.ts` — the month conversion across zones and
  its UTC fallback, the month boundaries including both Gregorian century rules, and the selection
  including a week that straddles a month boundary — and `frontend/tests/MonthlyPlanView.test.tsx`,
  which asserts that each item shows its reason, that a settled item keeps its place and is marked in
  words, that **no button of any kind is rendered**, that nothing is counted, and that no copy
  describes the learner rather than an item or the plan.
- **This change has been exercised against the production standalone frontend with a contract-shaped
  stub API, with JavaScript disabled**, as ADR-015 through ADR-021 and ADR-023 through ADR-025 each
  were. **Seventy-two checks passed**, with the unreachable-API panel confirmed separately
  afterwards. The run enforced "no JavaScript" by never running any: it issued raw HTTP requests and
  read the served HTML, so a control that only worked once hydrated could not have passed. The
  standalone server ran with `TZ=UTC`, and the stub's fixture dates were relative to the day of the
  run — the trap ADR-025's run recorded.

  Verified: `/plan/month` renders in the standalone build and names **the learner's own month**, with
  two learners in `Pacific/Kiritimati` and `Pacific/Midway` each shown theirs while the server was on
  UTC; the month's dated days render with each item's topic, subject, action in words, estimate, and
  the reason the plan gave for it; **completed, skipped, and postponed items each keep their place**
  and are marked in words; a week **straddling the month boundary** shows its item on the month's last
  day and leaves the next month's off the screen entirely; the roadmap topics the week has not dated
  are listed with their own reasons; the note naming how far the plan dates work appears when the week
  ends inside the month and **not** when it runs past it.

  **The read-only decision was verified structurally**: the page renders **no `<button>` and no
  `<form>` at all** — no completion, skip, postpone, return-to-planned, generate, or adapt control.
  **The screen issued no write**: every API request it made was a `GET`, to only the four catalogued
  reads, never touching PLN-004, PLN-001, or PLN-005, and none carried a `learner_id`.

  Also verified: no percentage, completion count, streak, or total appeared, and no copy described the
  learner rather than an item or the plan; all four empty states rendered — no goal, no plan, a month
  with no dated work, and a roadmap the week reaches the end of — as did the unreachable-API panel;
  `/plan`, `/plan/today`, and `/` each link to the new screen and it links back; `/plan` no longer
  says monthly is unbuilt; **the existing flow is untouched**, with the daily view still offering all
  three controls and `/plan` still carrying its forms; and **no API address appeared** in the HTML of
  `/plan/month`, `/plan`, `/plan/today`, or `/`, nor in any of the eleven client scripts they load.

  **Two assertions failed on the first runs and both were defects in the harness, not the product** —
  the pattern ADR-021, ADR-024, and ADR-025 each recorded. The stub's weekly plan ended after the
  month, so the branch saying the rest of the month has no dates was never reached; and the
  fully-dated-roadmap fixture held one topic more than the week dated, so something was always ahead.
  Both were fixture errors, fixed by splitting the straddling week into its own scenario.
- Open and deliberately not settled here: what a `monthly` plan type contains and whether one is ever
  written; whether the learner should be able to browse to another month; whether a plan should ever
  date work beyond one week; whether the four item panels should be factored into a shared component;
  and how a plan should report that a week cannot reach its horizon, which is FR-004's remaining
  criterion.
- Recorded as DEC-038 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-013: Model an examination period as a published window of reference data](ADR-013-examination-schedule-and-study-goal.md) — where `learners.timezone` and its default come from, and the horizon this month is shown against
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology this screen inherits
- [ADR-016: Fix the learner setup API contracts](ADR-016-learner-onboarding-api-contracts.md) — LRN-001, which carries the timezone this screen resolves a month with
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](ADR-020-initial-study-plan-generation.md) — the two plans this view reads, the seven dated days that constrain it, and the `monthly` plan type it leaves unwritten
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](ADR-021-plan-item-completion.md) — the status this screen shows and deliberately does not write
- [ADR-022: Adapt a study plan by rebuilding it around what happened](ADR-022-plan-adaptation.md) — the rebuilding this screen links to rather than performing
- [ADR-023: Show today's work as a reading of the weekly plan, not a daily plan](ADR-023-daily-study-view.md) — the record this one follows, and whose open question about a monthly view it answers
- [ADR-024: Let a learner skip a plan item, settling the item without retiring the topic](ADR-024-plan-item-skipping.md) — one of the settled statuses this screen marks in words
- [ADR-025: Let a learner postpone a plan item, settling it while the work waits for the next adaptation](ADR-025-learner-postponement.md) — the last of them, and the control this screen deliberately does not carry
- [API endpoint catalog](../api/endpoints.md) — the four contracts this screen consumes, none of which changes
- [Database schema](../database/schema.md) — `study_plans.plan_type`, whose `monthly` value stays unwritten
- [Domain model](../domain/domain-model.md) — the four plan levels, of which a monthly *plan* is still one this view is not
- [Terminology](../domain/terminology.md) — *monthly study view*, and the counts a plan may not carry
- [Functional requirements](../requirements/functional.md) — FR-003's second criterion, met in full
- [Coding standards](../development/coding-standards.md) — the UI responsibility rule that decides this record's central question
- [Repository and folder structure](../development/folder-structure.md) — where the route, the module, and its tests live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 3 item this closes
- [Architecture decision register](../architecture/decisions.md) — DEC-038
