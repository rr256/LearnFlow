---
title: "ADR-029: Show the Progress Overview as a Reading of What Is Stored, Counting Nothing of Its Own"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-14
related:
  - ../00-project-context.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-016-learner-onboarding-api-contracts.md
  - ADR-014-api-response-contract.md
  - ADR-017-topic-progress-api-and-schema.md
  - ADR-020-initial-study-plan-generation.md
  - ADR-021-plan-item-completion.md
  - ADR-022-plan-adaptation.md
  - ADR-023-daily-study-view.md
  - ADR-024-plan-item-skipping.md
  - ADR-025-learner-postponement.md
  - ADR-026-monthly-study-view.md
  - ADR-027-plan-feasibility.md
  - ADR-028-revision-workflow.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../api/versioning.md
  - ../database/schema.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../development/coding-standards.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../architecture/decisions.md
---

# ADR-029: Show the Progress Overview as a Reading of What Is Stored, Counting Nothing of Its Own

## Status

Accepted — 2026-08-14. Proposed 2026-08-14.

Accepted once the decision below was verified rather than merely argued. **Nothing in the decision
changed on acceptance**, and nothing is recorded here as unverified. The whole canonical check set is
green — the backend suite with warnings as errors (**901 passed**), Ruff lint and format, the frontend
lint, type check, **567 tests**, and production build, the `scripts/` checks, and the documentation
validator — and the **PostgreSQL integration tests were run locally** against the disposable
`learnflow_test` database (**1158 passed, none skipped**), with the development `learnflow` database
untouched and its row counts checked before and after to confirm it. The **scriptless
standalone-frontend run was performed** against a contract-shaped stub API with the server on
`TZ=UTC`: **89 checks passed**, plus **7** for the unreachable-API panel confirmed separately. The run
enforced "no JavaScript" by never running any — it issued raw HTTP requests and read the served HTML,
so a control that only worked once hydrated could not have passed.

Verified structurally rather than by inspection: `/progress` renders **no `<button>`, no `<form>`, and
no `<input>`**; **every request it issued was a `GET`**, to only the six catalogued reads, never
reaching PLN-001, PLN-004, PLN-005, REV-003, or REV-004, and none carried a `learner_id`; **nothing is
counted** — no percentage, `<progress>`, `<meter>`, streak, completion rate, or revision count appeared
— and no copy described the learner rather than an item, a plan, or a review. Also verified: each
plan's `item_count` and generation reason, today's work with its reason and action in words, the
outstanding-earlier-work note, the backend's own feasibility sentence, all three settled marks in
words, the due review and the exclusion of one whose day has not come, **all six empty states** and
the unreachable-API panel, navigation in both directions, that the daily and plan screens keep their
controls and the monthly view stays read-only, and that **no API address appeared** in the served HTML
or in any client script. Two learners 25 hours apart — `Pacific/Kiritimati` and `Pacific/Midway` — were
each shown **their own** date while the server ran on UTC, and a UTC learner matched the server's date.

Two of the harness's own assertions were found to be weak mid-run — one compared nothing and one was a
tautology — and were corrected and re-run before the figure above was recorded.

This delivers the **built part** of [FR-011](../requirements/functional.md#fr-011-progress-overview)
— the *progress overview*, the screen [terminology](../domain/terminology.md) has reserved the word
*dashboard* for since that vocabulary was written. It adds **no endpoint, no column, no table, no
migration, and no backend change at all**.

**FR-011 is not met in full**, and this record is explicit about which parts are not and why. See
[What FR-011 asks, and what this meets](#what-fr-011-asks-and-what-this-meets).

## Context

A learner's situation is now described in six places, with no single answer to *where am I*. Their
setup is on `/`, their plan and whether their week reaches their date are on `/plan`, today's work is
on `/plan/today`, the month is on `/plan/month`, their reviews are on `/revisions`, and their
recorded learning stages are beside topics in the curriculum view. Every fact exists; nothing gathers
them.

That gathering is FR-011, the last MVP requirement of Milestone 2 still wholly unbuilt, and the
terminology document had been holding a name for it. Before this change, its *Dashboard* row reserved
the word for "the progress overview FR-011 describes and PRG-001 will serve" and added "**None of
that is built.**" This change makes that second sentence false, which is the one documentation line
it directly contradicts — so the row is rewritten here, and neither quoted phrase survives in the
repository.

Six questions had to be answered, and the project owner decided each of them.
[ADR-014](ADR-014-api-response-contract.md) had already fixed the envelope and the error catalogue, so
none of that was open.

1. **Which existing facts the overview states.**
2. **Whether it is the home screen or a route of its own.**
3. **Which counts and summaries are permitted before a figure becomes a learner score.**
4. **Whether the existing reads suffice, or PRG-001 must be built.**
5. **How the empty, no-goal, no-plan, and unreachable-API states work.**
6. **Whether this needs an ADR.**

### One finding that shaped every answer

**Terminology had already ruled out most of what a dashboard usually shows, by name.**

Its *Plan coverage counts are not learner scores* section permits a count that describes **a plan** —
`item_count`, `remaining_topic_count`, `coverable_topic_count` — and forbids "no percentage complete,
no completion rate, no '14 of 60 done', no streak, no score, no total of a day, a week, or a plan."
Three further prohibitions are written against the exact figures a progress screen reaches for first:

> Nothing records when an item was skipped or why, and **nothing counts skips**.

> Wording that reads as a character description forms a view the product refuses, and **nothing counts
> postponements** anyway.

> **Nothing counts a learner's revisions**, and **no revision count appears in the interface at all**.

So the three headline numbers of a conventional dashboard — *completed*, *skipped and postponed*, and
*reviews due* — are between them either permitted only as a description of a plan or forbidden
outright. That decided question 3 before this record was written, and question 1 followed from it: an
overview that may not tally must **list and explain** instead.

## Decision

### The progress overview reads existing contracts; PRG-001 is not built

The screen consumes six existing reads — LRN-001, GOAL-002, PLN-002, PLN-003, PLN-006, and REV-001 —
through the same server-side client every view uses. **PRG-001, the catalogued
`GET /api/v1/progress/overview`, stays unimplemented.**

This is ADR-026's shape rather than ADR-027's, and the test is the one
[ADR-023](ADR-023-daily-study-view.md) set: a new endpoint is justified when the screen "needs
something the current reads cannot express". Feasibility met that bar because it joins the goal, the
week, the preferences, the roadmap, and every completed topic across the goal's history, and no
composition of reads yields it without the frontend planning. This screen meets no part of that bar:
every fact it states is already a field of a response, and the only work it does is filtering,
grouping, and choosing words.

**PRG-001 also promises more than this delivers.** Its catalogued purpose includes *priority focus
areas*, which need evidence — quiz outcomes, test results, mistakes — that nothing stores, and which
would be a ranking of topics that [terminology](../domain/terminology.md) refuses ("Nothing in
LearnFlow ranks two topics against each other"). Implementing PRG-001 as a public contract that
returns everything but the thing its name promises would fix a shape now that the missing half would
have to break later, which [versioning](../api/versioning.md#breaking-changes) makes expensive.

### The screen counts nothing of its own

Every figure on the screen is one an API response carried: a plan's `item_count`, and the counts and
durations PLN-006 returned. The frontend derives no number at all.

**No percentage, no ratio, no proportion, no rate, no streak, and no bar** — the stylesheet declines a
`<progress>` and a `<meter>` for the reason ADR-027 gave, that a bar is a percentage drawn rather than
written. **No completion count, no skip count, no postponement count, and no revision count**, each
forbidden by the passages quoted above.

What replaces them is a **list**. The items the learner has marked appear under the words for each
status — *Marked completed*, *Marked skipped*, *Marked postponed* — with the topic, the plan the mark
was made on, its day, and the reason the plan gave. A learner learns more from reading which topics
they set aside than from a number saying how many, and the reading cannot be compared against last
week, against a target, or against anybody else, which is the third of terminology's three tests.

**`item_count` is stated on its own, never against a second number.** "Your roadmap — 60 topics" is a
fact about a plan; "8 of 60" is the sentence terminology forbids verbatim.

### A route of its own, `/progress`; the home screen does not move

The overview is `app/progress/page.tsx`. `/` keeps its heading, *Your study setup*, and its role of
reading back what setup saved.

**The home screen was rejected as the location**, under *Alternatives*. Terminology's *Dashboard* row
fixes the home screen as "not a *dashboard*" and gives its UI heading; making it one would rewrite an
approved decision and relocate a shipped screen inside a change whose subject is a new one.

The canonical name is **progress overview** — FR-011's own title and PRG-001's path — rather than
*dashboard*, by the naming rule that a screen is named for what a learner does there rather than for a
UI genre. *Dashboard* remains the reserved informal word for this content, as terminology says; it is
not a route name, a heading, or a component name. The heading a learner reads is **"Where your study
stands"**.

### It writes nothing at all

`/progress` carries **no status control, no generate control, no adapt control, and no scheduling
control**. It renders no `<button>` and no `<form>`.

This is [ADR-026](ADR-026-monthly-study-view.md)'s read-only decision applied a second time, and for
the reason it gave: marking work belongs where a learner works. Every panel instead **names where its
action lives and links to it** — today's work to `/plan/today`, rebuilding to `/plan`, reviews to
`/revisions`, setup to `/setup`. Keeping one place per action is what stops a fifth surface acquiring
its own confirmation copy, its own `409` handling for a superseded plan, and its own place in every
future change to a control.

### The date is the learner's own, from `learnerToday`

The overview resolves the learner's calendar date from `learners.timezone` through the **same**
`learnerToday` the daily view uses and the monthly view derives from, with the same UTC fallback the
backend's `_today_for` applies. Three places derive a date from `learners.timezone` today — the
backend's `_today_for`, `learnerToday`, and `learnerMonth`, which ADR-026 recorded as a cost — and
**this screen adds no fourth**. Today's panel then calls
`selectDailyWork` — the daily view's own selection — so the two screens cannot disagree about which
day the learner is on, or about which earlier work is still outstanding.

**Overdue work is reported, not moved, and not counted.** The panel says work from earlier days is
still outstanding and links to the screen where the learner can act on it. Nothing writes a status and
nothing adapts, which keeps ADR-021's "only the named item moves" and ADR-022's "the learner asks"
both intact. The word describes the **item**; the learner is never behind.

### Only the goal's active plans are read

Marks made on a plan that has since been superseded are not shown. A superseded plan is history the
learner can no longer write into — PLN-004 refuses it with `409`, for every status — so listing its
marks under a heading inviting the learner to change them would offer something the API would reject.

### Five states, each said plainly

- **No goal** — a `Notice` pointing at `/setup`, because there is nothing to summarise until there is
  something to work toward.
- **No plan** — the standing panel says nothing has been generated and links to `/plan`; today's panel
  says the same in its own words.
- **Empty** — four further emptinesses, kept apart because they mean different things: a week that
  ended before today, a day the plan placed no work on (a day kept free, or one never set), a plan
  nothing has been marked on, and a learner with no reviews scheduled versus one whose reviews all
  have days still to come. With the two states above, that is **six** the panels distinguish, and the
  component tests assert each.
- **Unreachable API** — handled in the page rather than left to the route error boundary, because a
  production build replaces a server-side error message with a generic one. The `409` for more than
  one stored learner is explained separately, as every other screen explains it.
- **Loading** — a `Suspense` boundary declared inside `page.tsx` rather than as a `loading.tsx` segment
  file, for the reason [folder-structure.md](../development/folder-structure.md#frontendapp) records.

### What FR-011 asks, and what this meets

| Acceptance criterion | State after this change |
| --- | --- |
| View progress by subject and topic | **Not met.** Recorded learning stages stay where they are written, beside each topic in the curriculum view. Adding a stages-by-subject panel needs CUR-003 joined to PRG-002, which carries `subject_id` and no subject name; it was deliberately left out of this change. |
| View upcoming study tasks and revisions due | **Met.** Today's work from the active weekly plan, work from earlier days still outstanding, and the reviews REV-001 reports as due. |
| View priority focus areas based on available evidence | **Not met, and not buildable.** Nothing stores quiz outcomes, external test results, or mistake evidence, and ranking topics against each other is refused by terminology. |
| View recent quiz history and manually entered external test results | **Not met.** FR-009 and FR-010 do not exist; no quiz attempt or external test result is stored. |

**Do not write that FR-011 is complete.** One of its four criteria is met.

## Consequences

### Positive

- **A learner has one place that answers *where am I*.** Five facts that were spread across four
  screens are gathered without a seventh contract or a second copy of any rule.
- **No endpoint, no column, no table, no migration, and no backend file changes.** Nothing stored is
  reinterpreted and no public contract moves, so this change is reversible by deleting a route.
- **PRG-001 stays undecided rather than decided by accident**, keeping its shape free for the change
  that can also deliver the priority focus areas its purpose names.
- **The counting line is drawn in code and enforced by tests**, rather than left to review: the panel
  tests assert the absence of a percentage, a fraction, a streak, a `<progress>`, and a `<meter>`, and
  that no copy describes the learner.
- **One timezone conversion serves three screens.** `learnerToday` gains a third caller — after
  `/plan/today` and `/plan/month`, which reaches it through `learnerMonth` — rather than a third
  implementation, and `selectDailyWork` is reused rather than mirrored.
- **No AI provider is involved and no configuration variable is read.** The same records and the same
  instant produce the same overview.

### Negative

- **Another learner-facing route** is one more surface whose loading, empty, error, and success states
  must stay in step with six contracts rather than one.
- **The overview duplicates what other screens show.** Today's work appears here and on `/plan/today`;
  feasibility appears here and on `/plan`. That is what a summary is for, but it means a wording
  change to either now has two places to land — mitigated by rendering the *same components and the
  same selection function* rather than copies.
- **`/progress` makes six API calls**, the most of any screen. Each is a small read and four run
  concurrently, but it is the busiest page in the product.
- **A learner may want the number the screen refuses to show.** "How many topics have I finished?" is
  a reasonable question, and this record answers it with a list rather than a figure. The reasoning is
  terminology's and is quoted above, but the refusal will be felt.
- **The home screen is now one click from the thing most learners open the product for.** Whether `/`
  should eventually become this screen is left open rather than settled here.
- **Marks on superseded plans are invisible**, so a learner who adapts loses sight of what they marked
  on the plan that was set aside, even though PLN-003 can still read it.

### Neutral

- Nothing here totals, counts, ranks, or scores beyond the figures the API already returned.
- `monthly` and `daily` remain approved and unwritten `plan_type` values, as do `practice`, `revise`,
  and `review_mistakes` for `action_type`. `plan_items.status` and the revision statuses are untouched.
- Nothing adapts, generates, schedules, or marks on its own, and no learner flow changed: setup, the
  plan screens, the daily and monthly views, and the revision screen are all as they were, apart from
  one navigation link each.
- The backend is untouched: no route, no use case, no DTO, no domain rule, no model, no migration.
- `select_overdue` gains no new mirror. The frontend has exactly one — the settled set in
  `types/study-plan.ts`, which `selectDailyWork` reads — and this screen reuses that function rather
  than restating the rule.

## Alternatives considered

### Implement PRG-001 as a backend aggregation endpoint

`GET /api/v1/progress/overview`, composing the plan, the revisions, the feasibility reading, and the
learner's stages into one response.

**Not selected:** it fails ADR-023's test — every fact is already a field of an existing response, and
the endpoint would add no capability, only a second place for the same data to be assembled. It is
also a public contract that is breaking to change afterwards, and its catalogued purpose promises
priority focus areas that nothing can supply, so the shape fixed now is the shape that would have to
break when the evidence arrives. One round trip instead of six is a real gain and the only argument
for it; six small concurrent reads on a local single-learner installation do not pay for a permanent
contract.

### Make the overview the home screen

Replace `/` with this content, and move the setup summary to `/setup` or beneath it.

**Not selected:** terminology fixes the home screen as showing the saved learner setup and states
plainly that it "is not a *dashboard*", giving its UI heading. Overturning that is a decision about
the product's landing screen, not a side effect of adding a progress screen — and it would move a
shipped screen inside a change whose subject is a new one. It stays open: if the overview proves to be
what a learner opens LearnFlow for, promoting it is a route change with its own record.

### Show counts — completed, skipped, postponed, reviews due

Four figures across the top, which is what a dashboard usually is.

**Not selected**, and this is the alternative the record exists to refuse. Terminology forbids three of
the four by name — "nothing counts skips", "nothing counts postponements", "no revision count appears
in the interface at all" — and the fourth, stated beside a total, is the forbidden "14 of 60 done". A
count of completed topics *is* permitted as a plan coverage count when a plan reports it about itself,
which is what `completed_topic_count` on PLN-005 does; that is a description of an adaptation the
learner just asked for, not a standing figure on a screen. Read as a permanent number beside the
learner's name, it becomes exactly the measurement of a person the third test rules out.

### Add a progress bar or a percentage of the roadmap

"You have covered 12% of your roadmap", or a bar drawn from `item_count`.

**Not selected:** the single thing terminology forbids most explicitly. A bar is the same number drawn,
so the stylesheet declines one, as ADR-027's does.

### Include a learning-stages-by-subject panel

Read PRG-002 and CUR-003, group the learner's recorded stages by subject, and list them — FR-011's
first acceptance criterion.

**Not selected for this change**, by the project owner's decision at the delivery gate. It adds a
sixth data source and a join for a fact already visible where it is recorded, and it would need care to
list stages without tallying them per subject, which would be a learner score. It is a compatible
addition: the panel is additive, needs no contract change, and would meet FR-011's first criterion when
it lands.

### Show marks from superseded plans as well

Read PLN-002 without the `status=active` filter and list everything the learner has ever marked.

**Not selected:** it is an unbounded read that grows with every adaptation, and it would list marks
under a heading inviting change on records PLN-004 refuses with `409`. Plan history is readable through
PLN-003 for a learner who wants it; a summary of *where I am now* is about the plans being worked from
now.

## Implementation notes

- **No backend file changes.** The screen consumes LRN-001, GOAL-002, PLN-002, PLN-003, PLN-006, and
  REV-001 exactly as catalogued in [api/endpoints.md](../api/endpoints.md), which stays authoritative
  for their fields and error codes. No API client function was added: all six already existed.
- The route is `frontend/app/progress/page.tsx`, `force-dynamic` for the reason `/plan/today` and
  `/plan/month` are — it is a screen about the learner's current date, so a cached copy would be wrong
  from the first midnight after a build.
- `frontend/features/progress/overview.ts` holds `selectMarkedWork`, `describePlanType`, and
  `selectDueReviews` — plain functions over plain values, tested without a running server. Its module
  docstring records that the list lengths it uses to decide whether a panel has content never reach the
  screen.
- `frontend/features/progress/StudyProgressOverview.tsx` renders the five panels with its CSS Module,
  reusing `describeAction`, `describeEstimate`, `describeSettledStatus`, and `itemClassName` from
  `planner/plan.ts`, `selectDailyWork` and `weekHasPassed` from `planner/today.ts`, and the
  `PlanFeasibility` component unchanged. It renders no control. `DailyStudyView.tsx`,
  `MonthlyPlanView.tsx`, `PlanWeek.tsx`, `StudyRoadmap.tsx`, and `RevisionList.tsx` are untouched:
  extracting a shared item component from five panels is a refactor, and this is a feature change — the
  same call ADR-023 through ADR-026 each made.
- Covered by `frontend/tests/progress-overview-selection.test.ts` — the grouping, the unrecognised
  status, two items naming one topic on two plans, and that `is_due` is read rather than derived — and
  `frontend/tests/StudyProgressOverview.test.tsx`, which asserts each panel's content and reason, that
  **no `<button>` and no `<form>` is rendered**, that **nothing is counted** (no percentage, no
  fraction, no streak, no `<progress>`, no `<meter>`, no revision count), that no copy describes the
  learner, and each of the six empty states.
- Open and deliberately not settled here: whether the overview should become the home screen; whether a
  learning-stages-by-subject panel should be added; what PRG-001 returns if it is ever built, and
  whether this screen would then consume it; and whether marks on superseded plans should be readable
  anywhere in the interface.
- Recorded as DEC-041 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the envelope and error catalogue the six reads answer in, which this record did not have to reopen
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology this screen inherits
- [ADR-016: Fix the learner setup API contracts](ADR-016-learner-onboarding-api-contracts.md) — LRN-001, which carries the timezone this screen resolves a date with
- [ADR-017: Record manual topic progress as a learner-owned stage](ADR-017-topic-progress-api-and-schema.md) — the stages this screen deliberately does not gather, and where they are shown instead
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](ADR-020-initial-study-plan-generation.md) — the two plans this screen summarises, and the `item_count` it states
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](ADR-021-plan-item-completion.md) — the marks this screen lists and deliberately does not write
- [ADR-022: Adapt a study plan by rebuilding it around what happened](ADR-022-plan-adaptation.md) — the rebuilding this screen links to rather than performing
- [ADR-023: Show today's work as a reading of the weekly plan, not a daily plan](ADR-023-daily-study-view.md) — the selection and the timezone conversion this screen reuses, and the endpoint test it applies
- [ADR-024: Let a learner skip a plan item, settling the item without retiring the topic](ADR-024-plan-item-skipping.md) — one of the three marks this screen lists and never counts
- [ADR-025: Let a learner postpone a plan item, settling it while the work waits for the next adaptation](ADR-025-learner-postponement.md) — the last of them
- [ADR-026: Show the month as a reading of the roadmap and the week, not a monthly plan](ADR-026-monthly-study-view.md) — the read-only shape and the frontend-only reading this record follows
- [ADR-027: Report whether the saved week reaches the horizon, as a read-only planning rule](ADR-027-plan-feasibility.md) — the panel this screen renders unchanged, and the counts-not-ratios rule it applies
- [ADR-028: Schedule revisions from finished work, on the learner's ask](ADR-028-revision-workflow.md) — the reviews this screen shows as ready, and the count it may not state
- [API conventions](../api/conventions.md) — the envelope and the error codes the reads answer in
- [API endpoint catalog](../api/endpoints.md) — the six contracts this screen consumes, none of which changes, and PRG-001, which stays unimplemented
- [API versioning](../api/versioning.md) — what would make a change to PRG-001 breaking, had it been fixed here
- [Database schema](../database/schema.md) — the tables this reads through the API and does not alter
- [Terminology](../domain/terminology.md) — *dashboard*, *home screen*, and the counts a screen may not carry
- [Functional requirements](../requirements/functional.md) — FR-011, one of whose four criteria this meets
- [Coding standards](../development/coding-standards.md) — the UI responsibility rule that keeps every calculation in the backend
- [Repository and folder structure](../development/folder-structure.md) — where the route, the module, and its tests live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 2 item this advances
- [Architecture decision register](../architecture/decisions.md) — DEC-041
