---
title: "ADR-023: Show Today's Work as a Reading of the Weekly Plan, Not a Daily Plan"
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
  - ADR-024-plan-item-skipping.md
  - ADR-025-learner-postponement.md
  - ADR-026-monthly-study-view.md
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

# ADR-023: Show Today's Work as a Reading of the Weekly Plan, Not a Daily Plan

## Status

Accepted — 2026-08-09. Proposed 2026-08-09.

Accepted once the decision below was verified rather than merely argued. The whole check set is
green, and the run ADR-015 through ADR-021 each carried was completed rather than deferred: the
production standalone frontend was exercised against a contract-shaped stub API with JavaScript
disabled, and **fifty checks passed**. See [Implementation notes](#implementation-notes) for what that
run demonstrated. **Nothing is recorded here as unverified.**

This delivers part of
[FR-003](../requirements/functional.md#fr-003-study-timeline-and-plan)'s second acceptance criterion
— "the learner can view monthly, weekly, and daily recommendations" — for the **daily** half only.
Monthly is untouched. It adds no endpoint, no column, no table, and **no migration**.

## Implementation status — 2026-08-10

*Note added 2026-08-10. The decision below is unchanged; this records the one statement it made that
has since moved, and the cost it predicted being paid.*

**Two statements above are overtaken.**

- Under [Consequences](#neutral) — "`monthly`, `daily`, `practice`, `revise`, `review_mistakes`, and
  `skipped` all remain constrained and unwritten." **`skipped` is now written**, by PLN-004, per
  [ADR-024](ADR-024-plan-item-skipping.md). The other five remain exactly as this record left them,
  and no `daily` plan is written.
- Under [Decision](#the-classification-is-mirrored-for-display-the-domain-rule-stays-authoritative) —
  "The frontend restates its **three** boundaries — an item dated today is not overdue, an undated
  item never is, and completed work never is." There are now **four**, the fourth being that skipped
  work never is; `select_overdue` and the display partition both state it.

**The duplication this record recorded as a cost has now been paid once.** It said under *Negative*
that "the overdue rule now exists in two places … Changing the boundaries means changing both".
ADR-024 changed the boundaries, and both moved together: `select_overdue`'s `is_done` became
`is_settled` in the domain, and `isOutstanding` in `features/planner/today.ts` gained the matching
clause. The prediction held, and so did the mitigation — each has its own test.

**A skipped item behaves on this screen as the decision above implies.** It keeps its place in
today's list with the controls to take the skip back, because "the plan is the record of what the day
held"; and it does **not** appear under *From earlier days*, because that heading is for work still
outstanding and a skip is the learner having answered. Nothing on this screen writes a status the
learner did not ask for, and nothing still adapts on its own.

## Implementation status — 2026-08-11

*Note added 2026-08-11. The decision below is unchanged; this records the boundary count that has
moved again, and the second payment of the cost this record predicted.*

**Two statements are overtaken, both of them counts.**

- Under [Decision](#the-classification-is-mirrored-for-display-the-domain-rule-stays-authoritative) —
  the frontend "restates its **three** boundaries". The 2026-08-10 note made that four; it is now
  **five**, the fifth being that work the learner has **postponed** is never overdue, per
  [ADR-025](ADR-025-learner-postponement.md).
- Under [Consequences](#neutral) — the list of values that "remain constrained and unwritten". Only
  `monthly`, `daily`, `practice`, `revise`, and `review_mistakes` remain; every value of
  `plan_items.status` is now written, and three of the four are written by a learner.

**The duplication has been paid a second time, and made cheaper.** This record said under *Negative*
that "the overdue rule now exists in two places … Changing the boundaries means changing both". They
changed again and both moved: `POSTPONED` joined `SETTLED_STATUSES` in the application, and
`isOutstanding` in `features/planner/today.ts` now reads a named `PLAN_ITEM_SETTLED_STATUSES` in
`types/study-plan.ts` rather than a condition written out beside each use. The duplication is not
removed — a frontend that cannot import from the backend cannot remove it — but it is one line per
side, and each still has its own test.

**A postponed item behaves on this screen as a skipped one does.** It keeps its place and its date in
today's list with the controls to take the postponement back, and it does **not** appear under *From
earlier days*, because that heading is for work still outstanding and a postponement is the learner
having answered. Nothing on this screen writes a status the learner did not ask for, nothing re-dates
an item, and nothing still adapts on its own — postponing here is a note to the next adaptation, which
the learner still asks for on `/plan`.

**A status this build does not recognise is still treated as outstanding**, which is the safe reading
of "nobody has said anything about this" and the reason the mirror is a set rather than "anything but
`planned`".

## Implementation status — 2026-08-13

*Note added 2026-08-13. The decision below is unchanged; this records that the first of the questions
it left open has been answered, and the one property it claimed that a later screen does not keep.*

**The open question is answered.** This record listed "whether a monthly view is a reading or a plan"
first among the things it deliberately did not settle.
[ADR-026](ADR-026-monthly-study-view.md) settles it the same way this record settled the daily one: a
**reading**. `/plan/month` groups the goal's active `roadmap` and `weekly` plans to the learner's own
calendar month, resolving that month through the very `learnerToday` this record added. It needed
**no endpoint, no column, no migration, and no backend change at all**.

**Two statements above are overtaken.**

- Under [Consequences](#negative) — "**FR-003's second criterion is still not met in full.** Monthly
  is not built, and a `daily` plan type is not written." Monthly is now built, so **the criterion is
  met in full**. The second half stands: no `daily` plan type is written, and no `monthly` one either.
- Under [Consequences](#positive) — "**A completed item behaves identically on all three screens.**
  The daily view reuses `PlanItemStatusControl`, so a plan item is a plan item wherever it is met." It
  does **not** behave identically on the fourth. ADR-026's monthly view is **read-only** by decision:
  it shows an item's settled status in words and offers no control, because a month is where a learner
  looks rather than where they work. That record carries the departure as its chief cost.

**The overdue rule did not move for a third time.** The monthly view makes no claim about what is
overdue — it has no *From earlier days* heading and no equivalent — so `select_overdue` gained no
fourth mirror. The duplication this record recorded as a cost is still two-sided.

**`monthly` joins the reading that is not a plan.** What a `monthly` plan *contains* is as undecided
as what a `daily` one contains, and ADR-026 says so in the same place and for the same reason this
record did.

## Context

[ADR-020](ADR-020-initial-study-plan-generation.md) generates a `roadmap` and a `weekly` plan, and
`/plan` renders both. [ADR-021](ADR-021-plan-item-completion.md) lets a learner mark any item
completed, and [ADR-022](ADR-022-plan-adaptation.md) lets them rebuild the plan around what happened.

What none of that gives a learner is an answer to *what do I do now*. `/plan` shows the whole week
above the whole roadmap — sixty ordered topics and seven dated days — and a learner opening it at
breakfast has to find their own date in a list before they can start. ADR-020 rejected a roadmap
alone for the same reason it names here: "a learner asking what to do on Monday would get an ordered
list of sixty topics."

Five questions had to be answered, and the project owner decided each of them.

1. **Whether this is a `daily` plan.** `daily` is an approved `plan_type`
   ([DEC-021](../architecture/decisions.md)) that nothing writes. ADR-020 left it "constrained and
   ungenerated", noting that "adding one is a use-case change rather than a migration".
2. **What "today" means, and who decides it.** `learners.timezone` is stored
   ([ADR-013](ADR-013-examination-schedule-and-study-goal.md)) and the backend already resolves its
   own dates through it, in `_today_for`.
3. **Whether work whose day has passed appears here.** A weekly plan goes stale and nothing re-plans
   it on its own (ADR-022).
4. **Where the screen lives.**
5. **Whether a new endpoint is needed.**

### One finding that shaped three of the answers

**Everything this view needs is already readable.** A weekly plan's items each carry
`scheduled_for`, `status`, and `recommendation_reason` through PLN-003, and the learner's timezone
comes back on LRN-001. So the day's work is a **selection** from records that exist, not a
computation over records that do not — which is what let this be built with no endpoint, no schema
change, and no write path of its own beyond the PLN-004 control it reuses.

## Decision

### The daily study view reads the weekly plan; it is not a `daily` plan

A *daily study view* is a **reading** of the goal's active `weekly` plan filtered to one date. No
`study_plans` row of type `daily` is written, none is read, and the `CHECK` that permits the value
stays exactly as `20260806_03` created it.

**This is the decision most at risk of being misread**, which is why it is recorded rather than left
in a route file. A future contributor meeting a screen called *today* will reasonably assume the
`daily` plan type behind it. There is none. What a `daily` plan *is* — whether it re-slices a day's
capacity, whether it holds `practice` items the week does not, whether generating one supersedes a
week — remains undecided, and settling it as a side effect of adding a screen is what ADR-020 refused
when it declined to deliver all four plan types at once.

The distinction is not merely internal. A generated `daily` plan would be a stored record with its
own `generation_reason`, its own supersede lifecycle, and its own rows accumulating on every
generation. A view has none of that: it goes stale only in the sense that the plan beneath it does,
and there is nothing to prune.

### "Today" is the learner's own date, resolved on the frontend from `learners.timezone`

The Next.js server reads LRN-001, converts the current instant into the learner's zone, and passes
one ISO `YYYY-MM-DD` string into the view. A zone that cannot be read falls back to UTC, which is the
fallback `_today_for` already applies for the reason it gives: a date a day out is a recoverable
annoyance, and refusing to render is not.

**The learner's zone, never the server's.** A container running in UTC must not show a learner in
`Asia/Kolkata` tomorrow's work at half past eleven at night. That is the boundary error
`learners.timezone` exists to prevent, and it is exactly where a daily view lands — a screen about a
date is wrong for a whole day when it picks the wrong one.

The conversion is a pure function taking the instant as an argument, so a test fixes one moment and
asserts exact dates across zones rather than asserting that the code agrees with itself. That is the
same property ADR-020 bought with the `Clock` port, obtained the same way.

### Work whose day has passed is shown, under its own heading, and nothing moves it

Items dated before today whose work has not happened appear in a second group, beneath today's, with
the day each was placed on. Completed work does not appear there — the question is whether the work
happened, not which status it holds.

**Showing it in the same list as today's was rejected.** The plan did not ask for that work today,
and a screen that implied otherwise would misstate the record it is rendering.

**Hiding it was also rejected.** A weekly plan goes stale, adaptation is something the learner asks
for, and a today-only view would hide precisely the work a learner most needs to see — leaving them
to discover it by scrolling the week they opened this screen to avoid.

**Nothing moves it.** No adaptation is triggered, no status is written, and no item is re-dated. The
screen names the control that would carry the work forward and links to it. That keeps ADR-022's
accepted decision that "the learner asks; nothing adapts on its own", and ADR-021's that "only the
item moves" — a list that rearranged itself under a hand ticking it is the surprise both records
refused.

**The wording describes items, never the learner.** The heading is *From earlier days*; the copy says
the plan placed the work on days that have passed and that nothing has moved it. *Overdue* is correct
of an item and wrong of a learner, which [terminology](../domain/terminology.md) states outright, and
this is the first screen with any occasion to get it wrong.

### The classification is mirrored for display; the domain rule stays authoritative

`select_overdue` in `backend/app/domain/study_planning.py` remains the rule that decides what
adaptation writes. The frontend restates its three boundaries — an item dated today is not overdue,
an undated item never is, and completed work never is — to *group* items on a screen.

**This is the cost of the decision and is recorded as such.** The same rule now exists in two places.
It is accepted because the two do different things: one decides which rows are written `postponed`,
the other decides which heading a line appears under, and nothing on this screen writes anything. A
drift between them would show a learner an item under the wrong heading, not store a wrong status.
The alternative — a sixth endpoint returning the day's work — was rejected below.

### A new route, `/plan/today`; generation and adaptation stay on `/plan`

The daily study view is `app/plan/today/page.tsx`. `/plan` keeps the roadmap, the week, and the two
controls that rebuild a plan, and gains a link; the home screen gains one too.

Nesting it under `/plan` says in the address what the screen is: a reading of the plan. A top-level
`/today` would be shorter and would lose that. A panel on `/plan` would put the daily view behind the
generate and adapt controls on a screen that already carries four sections, and would leave a learner
no address to open directly.

**Neither generating nor adapting appears on this screen.** A daily view is where a learner works,
and putting a button that rebuilds the plan beside the list they are ticking would invite exactly the
accident ADR-022's "nothing adapts on its own" exists to prevent.

### No new endpoint

The screen reads LRN-001, GOAL-002, PLN-002, and PLN-003, and writes through PLN-004 — every one of
them an existing contract. **No sixth planning endpoint is added**, and nothing about the five
changes: no field, no status code, no path.

The reads go through the same server-side API client every view uses, and the completion control
posts to the existing `"use server"` module. The browser still issues no request to the backend, so
`API_CORS_ALLOWED_ORIGINS` stays planned rather than implemented. This inherits
[ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md) through ADR-022 rather than
renegotiating them, and the completion form works without JavaScript because it is the same form.

## Consequences

### Positive

- **A learner has somewhere to start.** The screen answers *what do I do now* with a short list they
  can act on, which is what FR-003's daily recommendation asks for and what neither the roadmap nor
  the week gave.
- **No endpoint, no column, no table, no migration.** Nothing stored is reinterpreted and no public
  contract changes, so this change is reversible by deleting a route.
- **Missed work becomes visible without becoming automatic.** A learner sees what has not happened
  and still chooses when to rebuild the plan around it.
- **A completed item behaves identically on all three screens.** The daily view reuses
  `PlanItemStatusControl`, so a plan item is a plan item wherever it is met.
- **The `daily` plan type stays undecided rather than decided by accident**, and this record says so
  in a place a contributor will find before writing one.

### Negative

- **The overdue rule now exists in two places** — `select_overdue` in the domain and the display
  partition in `features/planner/today.ts`. Changing the boundaries means changing both, and only one
  of them has a test that would fail if the other moved.
- **"Today" is resolved by a client of the API rather than by the API.** The frontend and the backend
  agree today because both read `learners.timezone` and both fall back to UTC; nothing enforces that
  they keep agreeing.
- **The screen shows a day, not a plan.** A learner whose week ran out sees an explanation and a link
  rather than work — an honest state, but a screen that cannot fill itself.
- **A fourth learner-facing route** is another surface that must keep its loading, empty, error, and
  success states in step with the contract behind it.
- **FR-003's second criterion is still not met in full.** Monthly is not built, and a `daily` plan
  type is not written.

### Neutral

- Nothing here totals, counts, ranks, or scores. No completion count, no "3 of 7", no percentage, no
  streak — the line [terminology](../domain/terminology.md#plan-coverage-counts-are-not-learner-scores)
  draws.
- No AI provider is involved, and no new configuration variable is read.
- `monthly`, `daily`, `practice`, `revise`, `review_mistakes`, and `skipped` all remain constrained
  and unwritten, exactly as ADR-020 and ADR-022 left them.
- The domain layer still holds one module, and the backend is untouched by this change.

## Alternatives considered

### Generate a `daily` plan record

Write a `study_plans` row of type `daily` for each day, with its own items and its own
`generation_reason`, alongside the roadmap and the week.

**Not selected:** it settles what a monthly and a daily plan *are* as a side effect of adding a
screen, which is the trade ADR-020 refused when it declined all four plan types at once. It would
also duplicate every weekly item into a second plan, making `item_count` ambiguous and giving a
learner two rows to complete for one session — the same objection ADR-022 raised against carrying
completed items forward.

### A sixth endpoint returning the day's work

`GET /api/v1/study-plans/today`, computing the learner's date with `_today_for` and the partition with
`select_overdue`, so the rule lives in one place.

**Not selected:** it is a public contract that is breaking to change afterwards
([versioning](../api/versioning.md#breaking-changes)), for a screen that adds no capability the four
existing reads cannot serve. The rule it would centralise decides a heading rather than a stored
value. If the daily view later needs something the current reads cannot express — a `daily` plan, or
a day's work across several plans — that is the change that should introduce the endpoint, with the
decision it carries.

### Resolve "today" from the frontend server's own clock and zone

Read `new Date()` and format it with the process's zone.

**Not selected:** it is wrong by a day for any learner whose zone differs from the container's, which
is the specific failure `learners.timezone` was introduced to prevent. It would also make the screen's
correctness depend on a deployment detail no test could see.

### Show only work dated today

The strictest reading of "what should I study today", and it would keep the overdue rule entirely in
the backend.

**Not selected:** a weekly plan goes stale and nothing re-plans it on its own, so a learner who missed
Monday would open this screen on Wednesday and see no sign of it. The work would still be in the plan,
still uncompleted, and invisible on the one screen they opened to find out what to do.

### A panel at the top of `/plan`

No new route, no extra round trips — the weekly plan is already read there.

**Not selected:** `/plan` already carries the generate control, the adapt control, the week, and the
roadmap. A daily view added to it is a fifth section rather than a place to go, and it would sit
beside two buttons that rebuild the plan, on the screen a learner opens to tick items off.

## Implementation notes

- No backend file changes. The screen consumes LRN-001, GOAL-002, PLN-002, PLN-003, and PLN-004
  exactly as catalogued in [api/endpoints.md](../api/endpoints.md#planning-endpoints), which stays
  authoritative for their fields and error codes.
- The route is `frontend/app/plan/today/page.tsx`, `force-dynamic` — more strongly than the other
  routes, because a page about the current date would be wrong from the first midnight after a build.
  It declares its own `Suspense` boundary inside `page.tsx` rather than a `loading.tsx` segment file,
  for the reason [folder-structure.md](../development/folder-structure.md#frontendapp) records.
- `frontend/features/planner/today.ts` holds `learnerToday`, `selectDailyWork`, and `weekHasPassed` —
  plain functions taking the instant as an argument, so they are tested at fixed moments across zones
  without a running server. `learnerToday` assembles its result from `Intl.DateTimeFormat`'s
  `formatToParts` rather than from a formatted string, so it does not depend on how a locale orders or
  separates the parts.
- `frontend/features/planner/DailyStudyView.tsx` renders both groups and reuses
  `PlanItemStatusControl`, `describeAction`, `describeEstimate`, and `itemClassName` from the existing
  planner module. `PlanWeek.tsx` and `StudyRoadmap.tsx` are untouched: extracting a shared item
  component from three panels is a refactor, and this is a feature change.
- Covered by `frontend/tests/daily-plan-selection.test.ts` — the date conversion across four zones,
  its UTC fallback, and the three overdue boundaries — and
  `frontend/tests/DailyStudyView.test.tsx`, which asserts that each item shows its reason and its
  control, that a completed item keeps its place, that nothing is counted, and that no copy on the
  screen describes the learner rather than an item.
- **This change has been exercised against the production standalone frontend with a contract-shaped
  stub API, with JavaScript disabled**, as ADR-015 through ADR-021 each were. **Fifty checks passed**,
  on the first run. The run enforced "no JavaScript" by never running any: it issued raw HTTP requests
  and submitted the completion form as a scriptless browser does — a native multipart POST to the
  page's own URL carrying the `$ACTION_*` fields Next.js renders — so a control that only worked once
  hydrated could not have passed. The standalone server ran with `TZ=UTC`, so every date the screen
  showed can only have come from the stored timezone.

  Verified: **the learner's own date, not the server's** — two renders over identical plan data
  differing only in `learners.timezone` produced different days, and the run landed on a real
  boundary, with a learner in `Pacific/Kiritimati` shown 2026-08-10 while the server was on
  2026-08-09; today's planned and completed items both rendered, each with the reason the plan gave
  for it, its action in words, and its estimate; work whose day had passed appeared under *From
  earlier days* headed by its own date, while a passed day with nothing outstanding and a day still to
  come were both absent; no percentage, completion count, or total appeared, and no copy described the
  learner rather than an item; the completion form carried `method="POST"`,
  `encType="multipart/form-data"`, and an empty `action`, with the status it would set and nothing
  about *when*; a no-JavaScript submission reached PLN-004 **exactly once**, at
  `/api/v1/plan-items/{id}` with the body `{"status":"completed"}` and nothing else; **only that item
  moved**, the overdue item still offering completion; the undo restored it; all four empty
  states rendered — a day the plan placed nothing on, a plan whose week had run out, a goal with no
  dated plan, and a learner with no goal — as did the unreachable-API panel; the screen offered no
  generate and no adapt control, and `/plan` and `/` both linked to it; and **no API address appeared
  in the HTML of `/plan/today`, `/plan`, `/`, `/setup`, or `/curriculum`, nor in any of the thirteen
  client scripts they load**.
- Open and deliberately not settled here: what a `daily` plan type contains and whether one is ever
  written; whether a monthly view is a reading or a plan; whether the overdue partition should later
  move behind an endpoint; and whether this screen should ever surface revision work, which does not
  exist.
- Recorded as DEC-035 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-013: Model an examination period as a published window of reference data](ADR-013-examination-schedule-and-study-goal.md) — where `learners.timezone` and its default come from
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology this screen inherits
- [ADR-016: Fix the learner setup API contracts](ADR-016-learner-onboarding-api-contracts.md) — LRN-001, which carries the timezone this screen resolves a date with
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](ADR-020-initial-study-plan-generation.md) — the weekly plan this view reads, and the `daily` plan type it leaves unwritten
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](ADR-021-plan-item-completion.md) — the control this screen reuses unchanged
- [ADR-022: Adapt a study plan by rebuilding it around what happened](ADR-022-plan-adaptation.md) — the overdue rule this view mirrors for display, and the adaptation it links to rather than performing
- [ADR-024: Let a learner skip a plan item, settling the item without retiring the topic](ADR-024-plan-item-skipping.md) — the status this screen's control gained, and the boundary change both halves of the mirrored rule absorbed
- [ADR-025: Let a learner postpone a plan item, settling it while the work waits for the next adaptation](ADR-025-learner-postponement.md) — the fifth boundary, and the third control this screen now carries
- [API endpoint catalog](../api/endpoints.md) — the five contracts this screen consumes, none of which changes
- [Database schema](../database/schema.md) — `study_plans.plan_type`, whose `daily` value stays unwritten
- [Domain model](../domain/domain-model.md) — the four plan levels, of which a daily *plan* is still one this view is not
- [Terminology](../domain/terminology.md) — *daily study view*, and why an item is overdue and a learner never is
- [Functional requirements](../requirements/functional.md) — FR-003's daily recommendation
- [Coding standards](../development/coding-standards.md) — the UI responsibility rule this view stays inside
- [Repository and folder structure](../development/folder-structure.md) — where the route, the module, and its tests live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 3 item this partly closes
- [Architecture decision register](../architecture/decisions.md) — DEC-035
