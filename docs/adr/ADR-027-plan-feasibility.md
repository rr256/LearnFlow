---
title: "ADR-027: Report Whether the Saved Week Reaches the Horizon, as a Read-Only Planning Rule"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-13
related:
  - ../00-project-context.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-013-examination-schedule-and-study-goal.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-018-weekly-availability-slots.md
  - ADR-019-study-goal-planning-preferences.md
  - ADR-020-initial-study-plan-generation.md
  - ADR-021-plan-item-completion.md
  - ADR-022-plan-adaptation.md
  - ADR-023-daily-study-view.md
  - ADR-024-plan-item-skipping.md
  - ADR-025-learner-postponement.md
  - ADR-026-monthly-study-view.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../api/versioning.md
  - ../database/schema.md
  - ../domain/domain-model.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../development/coding-standards.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../architecture/decisions.md
---

# ADR-027: Report Whether the Saved Week Reaches the Horizon, as a Read-Only Planning Rule

## Status

Accepted — 2026-08-13. Proposed 2026-08-13.

Accepted once the decision below was verified rather than merely argued. **Nothing in the decision
changed on acceptance**, and nothing is recorded here as unverified. The whole canonical check set is
green — the backend suite with warnings as errors (**788 passed**), Ruff lint and format, the frontend
lint, type check, **480 tests**, and production build, the `scripts/` checks, and the documentation
validator. The **PostgreSQL integration tests were run locally** against the disposable
`learnflow_test` database (**237 passed**), with the development `learnflow` database untouched and
checked afterwards to confirm it. The **scriptless standalone-frontend run was performed** against a
contract-shaped stub API with the server on `TZ=UTC`: **54 checks passed**, plus the unreachable-API
panel confirmed separately. See [Implementation notes](#implementation-notes) for what the run
demonstrated.

This completes [FR-004](../requirements/functional.md#fr-004-plan-adaptation)'s **third** acceptance
criterion — "the updated plan preserves target-date awareness and highlights meaningful trade-offs
when time is insufficient" — which is the **last unmet acceptance criterion of FR-004**, and the one
[ADR-020](ADR-020-initial-study-plan-generation.md), [ADR-022](ADR-022-plan-adaptation.md),
[ADR-024](ADR-024-plan-item-skipping.md), [ADR-025](ADR-025-learner-postponement.md), and
[ADR-026](ADR-026-monthly-study-view.md) have each named, in turn, as unbuilt.

It adds **no column, no table, and no migration**. It adds one public read contract, PLN-006, and the
**fourth rule** in the domain layer.

## Context

Five accepted records have now closed with the same sentence in their open items: *how a plan should
report that a week cannot reach its horizon*. ADR-020 recorded it under *Negative* — "**A plan can be
generated that the learner's week cannot deliver**, and nothing says so beyond the roadmap running to
the horizon while the week reaches only a few topics." ADR-022 narrowed it without closing it: "An
adapted plan says how much is left, not whether it fits."

So today a learner can save thirty minutes a week against a six-month horizon and sixty topics, and
LearnFlow will generate them a roadmap, place a week, adapt around what they miss, and never once
mention that the arithmetic does not work. Everything the product says is true; the one thing it
does not say is the thing that matters most.

Six questions had to be answered, and the project owner decided each of them.
[ADR-014](ADR-014-api-response-contract.md) had already fixed the envelope and the error catalogue, so
none of that was open.

1. **What the calculation is, and what it assumes.**
2. **Which layer owns it** — a screen, the application, or the domain.
3. **Where the result appears, and whether it is stored or read live.**
4. **Whether the existing reads suffice.**
5. **How a missing horizon or a missing week is explained.**
6. **Whether this needs an ADR.**

### One finding that shaped every answer

**The terminology document had already decided the hardest part, and against the obvious reading.**
Its *Terms to Avoid* table ruled out "weekly study hours; total available time", with this reason —
quoted here as it stood **before** this change, which amends the row to record where the judgement now
lives:

> A total is planning arithmetic, and it invites a judgement about whether a week is *enough*.
> **FR-003's planner is what should form that** [judgement].

That is not a prohibition on this feature. It is an instruction about **where it belongs**: totalling
a learner's week is forbidden as a statistic and required as a planning rule. The same document's
*Plan coverage counts are not learner scores* section then fixes how the answer may be expressed —
"always reported **as a count**, never as a ratio or a proportion, because a ratio has a denominator
and a denominator invites the comparison" that turns a description of work into a measurement of a
person.

Between them, those two passages decided the layer and the vocabulary before this record was written.

## Decision

### The rule is a pure domain function, and the arithmetic lives nowhere else

`assess_horizon_coverage` joins `order_by_syllabus`, `schedule_sessions`, and `select_overdue` in
`backend/app/domain/study_planning.py`. It takes plain values — a count of remaining topics, a session
length, seven minute counts, and two dates — and returns counts and durations. No clock, no session,
no configuration.

**This is where this record departs from ADR-026**, and the departure is the point. The monthly study
view is a frontend reading that deliberately performs no arithmetic, because
[coding-standards.md](../development/coding-standards.md#ui-responsibilities) reserves planning for
the backend. Feasibility *is* that arithmetic. A screen that summed a week would be the second planner
ADR-026 refused to build, and it would be summing it to answer precisely the question terminology.md
says the planner must answer.

**A whole span is counted by weekday rather than walked day by day.** A goal aimed years out would
otherwise mean an unbounded loop; counting how often each weekday falls in the span is exact, is seven
multiplications, and is the same sum in a different order. A test asserts the two agree over a
six-month horizon rather than leaving it argued.

### The calculation, and the assumptions it states

`required = remaining topics × session length`. `available = Σ (occurrences of each weekday in the
span) × that day's saved minutes`. The verdict is `available ≥ required`.

Four assumptions are decided here rather than discovered, and each is reported in the response so a
learner can see what was assumed:

- **One session per remaining topic.** That is what generation places, so feasibility measures the
  plan the product would actually build.
- **Both ends of the span count.** Today can still be studied, and so can the horizon day — the same
  boundary `select_overdue` fixes when it rules that today is not behind.
- **The horizon is ADR-020's**, the earlier of the examination window's first sitting day and the
  target date. Feasibility and generation therefore aim at the same date by construction.
- **A settled-but-unfinished topic still needs time.** Only a `completed` topic is excluded, which is
  ADR-022's exclusion exactly. A skipped or postponed topic is planned again, so pretending it needs
  no time would flatter the answer.

**Remaining work is read from the active roadmap, not the curriculum**, so it is the same set
adaptation would re-plan. A goal with no active roadmap reports nothing remaining rather than falling
back to the whole curriculum: a plan that does not exist cannot be short of time.

### It is a live read, and it writes nothing

PLN-006 is a `GET`. Asking writes no plan, no availability, no preference, and no item status, and
triggers no adaptation. A learner may ask as often as they like.

**Writing the sentence into `generation_reason` was rejected**, under *Alternatives*, and this is the
decision most worth stating plainly. ADR-020 fixes that a plan's reasons are "written when the plan is
generated and never rewritten" — which is right for a plan's own history and exactly wrong here. A
learner who reads "you are eighteen hours short", edits their week, and returns would still read
eighteen hours short, because the sentence was frozen. The answer has to move when its inputs move,
and only a live read does that.

### A new endpoint, goal-scoped, because the existing reads cannot express it

`GET /api/v1/study-goals/{study_goal_id}/plan-feasibility`. Goal-scoped as PLN-005 is: the horizon,
the week, and the preferences all belong to the goal.

**This is the case ADR-023 anticipated.** It rejected a sixth planning endpoint for the daily view
"for a screen that adds no capability the four existing reads cannot serve", and said so conditionally:
"If the daily view later needs something the current reads cannot express … **that is the change that
should introduce the endpoint, with the decision it carries.**" Feasibility joins the goal, the saved
availability, the preferences, the active roadmap, and every completed topic across the goal's whole
history. No composition of PLN-002, PLN-003, GOAL-002, and LRN-001 yields it without the frontend
doing the planning.

**It takes no request body and no query parameter.** Everything it reads is stored, so no caller can
ask about a week the learner never saved — the guarantee PLN-001 and PLN-005 both keep.

### Three verdicts, and `unknown` is an answer

`sufficient`, `insufficient`, or `unknown`, with `unknown_reason` naming which gap caused the third:
`no_horizon` for a goal aiming at neither an examination cycle nor a target date, and
`no_availability_saved` for a goal with no stored week.

**They are two gaps, not one, because they ask the learner for different things** — a date, or a week
— and the screen names a different next step for each. Collapsing them would leave it guessing.

**A week saved and deliberately kept free is neither.** That is zero minutes, which is a real answer
and yields `insufficient` with a clear explanation. Reporting it as unknown would erase the
distinction [ADR-018](ADR-018-weekly-availability-slots.md) exists to keep: a day kept free is a
statement, and a day never set is the absence of one.

**An unset session length is named as the planner's own choice**, never as a default, which is
[ADR-019](ADR-019-study-goal-planning-preferences.md)'s distinction and ADR-020's wording rule.
`session_minutes_chosen_by_planner` carries it, so the screen can say whose decision it was.

### Counts and durations, never a ratio

Every number in the response is a count or a duration. There is deliberately **no percentage, no
completion rate, and no proportion**, and `coverable_topic_count` sits beside `remaining_topic_count`
as two figures a caller states side by side — never as one over the other.

That is terminology.md's rule applied literally, and it is enforced on both sides: backend tests
assert no `%` and no `/` in the composed sentence, and the panel's tests assert that no percentage is
rendered and that the two counts never appear as a fraction. The stylesheet declines a progress bar
for the same reason — a bar is a percentage drawn rather than written.

**A shortfall is never a negative surplus.** `shortfall_minutes` is zero when the week is enough,
because "twelve hours spare" and "twelve hours short" are different statements and a sign is a poor
way to tell a learner which they are reading.

### The wording describes the plan and the time, never the learner

The sentence is composed in the use case, beside the numbers it quotes, as every other plan reason is.
A screen that assembled its own could disagree with the figures next to it.

When time is short it names **what the learner could change** — save more study time, shorten
sessions, or aim at a later date — because FR-004 asks for a *meaningful trade-off* rather than a
verdict. It never says the learner is behind, slow, or unrealistic; a week that does not reach a date
is arithmetic. Tests assert the absence of that wording rather than trusting review to catch it.

### It appears on `/plan`, above the week

`/plan` is where the plan and the controls that rebuild it live, and a learner deciding whether to
adapt is owed this before they read the days. It is **not** added to `/plan/today`, which is about one
day, nor to `/plan/month`, which ADR-026 fixed as read-only and horizon-adjacent already.

The panel renders through the same server-side client every view uses. No browser calls the API, so
`API_CORS_ALLOWED_ORIGINS` stays planned. It carries **no control of any kind**.

## Consequences

### Positive

- **FR-004 is met in full**, all three acceptance criteria, for the first time. Its third has been
  open since the requirement was written.
- **The product finally says the one thing it could not.** A learner whose week cannot reach their
  horizon is told, with the numbers, before they spend six months discovering it.
- **The answer stays true.** Because it is a live read rather than a stored sentence, editing the week
  and asking again gives the new answer.
- **No column, no table, no migration.** Every input was already stored, so no learner record is
  reinterpreted and no existing plan is touched.
- **The rule is exhaustively testable without a clock or a database**, as the other three domain rules
  are, and its shortcut is proved equal to the day-by-day walk rather than argued.
- **Generation and feasibility cannot drift on the horizon or the exclusion**, because both read
  `_horizon_of` and `list_completed_topic_ids` rather than reimplementing them.
- No new error code was needed: `not_found`, `validation_error`, and `conflict` all existed.

### Negative

- **A sixth planning endpoint is public contract**, and changing a field or a status code on it is
  breaking under [versioning](../api/versioning.md#breaking-changes). It is the first planning
  endpoint added since ADR-022, and ADR-023 set the bar it had to clear.
- **The response carries fourteen fields**, which is the widest in the planning group. Each is
  load-bearing for the explanation, but a client is entitled to all of them for ever.
- **`/plan` now makes four API calls where it made three.** The read is cheap — a handful of small
  queries — but the screen is the busiest in the product.
- **The assumption of one session per topic is coarse.** A topic needing three sessions and one
  needing half of one are counted alike, because nothing stores a per-topic estimate. The answer is
  therefore an estimate presented as arithmetic, and the response says what it assumed rather than
  claiming more precision than it has.
- **Nothing recomputes when availability changes.** GOAL-005 still touches only availability, by
  ADR-022's decision; the learner sees the new answer when they next open `/plan`, not before.
- **A learner may read `insufficient` and take it as a verdict** despite the wording. The copy is
  careful, the tests enforce it, and it remains a risk of saying anything at all about time.

### Neutral

- Nothing here totals, ranks, or scores. No percentage, no completion rate, no streak.
- No AI provider is involved, and no configuration variable is read. The same records and the same
  date produce the same answer.
- `monthly` and `daily` remain approved and unwritten `plan_type` values, as do `practice`, `revise`,
  and `review_mistakes`.
- Nothing adapts on its own, and no learner flow changed: setup, the daily study view, the three
  status verbs, and adaptation are all untouched.
- No command-line tool assesses feasibility.

## Alternatives considered

### Write the sentence into `generation_reason` at generation and adaptation

FR-004's literal wording is that the *updated plan* highlights the trade-off, and a plan already
carries a reason. No endpoint, no contract, no extra call.

**Not selected**, and this was the closest alternative. ADR-020 fixes that a plan's reasons are never
rewritten, which is right for history and fatal here: the moment a learner changed their week, the
sentence would be wrong, and the only way to refresh it would be to regenerate — destroying the plan
they were reading to fix a sentence about it. A stale answer to "will I make it?" is worse than none.
The two are not exclusive; if a stored snapshot is later wanted, it can be added beside this without
changing it.

### Compute it in the frontend from the existing reads

The goal carries availability and preferences, PLN-003 carries the roadmap. A component could sum the
week and divide.

**Not selected:** it is planning performed in the browser tier, which
[coding-standards.md](../development/coding-standards.md#ui-responsibilities) reserves for the
backend, and terminology.md names the planner as what should form this judgement. It would also
duplicate the horizon rule and the completed-topic exclusion with no way to keep them in step — the
duplication ADR-023 accepted for one boolean, taken up here for the whole calculation. And it could
not see completions on superseded plans, which PLN-003 does not return.

### Put the rule in the application layer rather than in `domain/`

Keep `study_planning.py` at three rules and write the arithmetic beside the use case.

**Not selected:** it is a rule a learner would recognise as part of their plan, it depends on nothing
outside itself, and `folder-structure.md` reserves that layer for "domain invariants and
calculations". It is the same argument ADR-020 made for the ordering and placement rules, and the same
one that made `select_overdue` pure.

### Report a percentage, or a progress bar

"Your week covers 71% of what is left" is shorter than two counts and immediately legible.

**Not selected:** it is the single thing terminology.md forbids most explicitly — "no percentage
complete, no completion rate … A plan-coverage count is always reported as a count, never as a ratio
or a proportion, because a ratio has a denominator and a denominator invites the comparison". A bar is
the same number drawn, so the stylesheet declines one too.

### Refuse the question when a horizon or a week is missing

Return `409`, or `422`, rather than an `unknown` verdict.

**Not selected:** a learner who has not finished setting up is asking a reasonable question, and an
error would tell them they did something wrong rather than what is missing. `unknown` with a named
reason lets the screen say which of the two gaps it is and link to the one control that closes it.

### Trigger the assessment from GOAL-005 when the week is saved

Answer at the moment the input changes, which is when the learner most wants to know.

**Not selected:** GOAL-005 promises to touch nothing but availability, which is ADR-022's decision
about adaptation applied to the same endpoint. A read the learner can take at any time serves the same
need without a write path acquiring an opinion.

## Implementation notes

- Endpoint fields and per-endpoint error codes are in
  [api/endpoints.md](../api/endpoints.md#planning-endpoints), which stays authoritative.
- **No migration.** Every input — the goal's horizon, `availability_slots`, the two preference
  columns, `study_plans`, and `plan_items.status` — was already stored.
- `assess_horizon_coverage` and `HorizonCoverage` are in `backend/app/domain/study_planning.py`, the
  fourth rule there. `DAYS_IN_WEEK` names the seven positions, and the module docstring records that
  which day name fills which position stays in the application layer (ADR-018).
- `FEASIBILITY_VERDICTS`, `UNKNOWN_REASONS`, and `PlanFeasibility` live in
  `application/dto/study_plan.py` beside the stored vocabularies, with a note that these are contract
  values rather than column values — nothing stores them.
- `ManageStudyPlans.assess_feasibility` serves the endpoint, with `_weekly_minutes`, `_unanswerable`,
  and `_feasibility_reason` beside it. `_horizon_of` and `list_completed_topic_ids` are reused
  unchanged, which is what keeps feasibility and adaptation aiming at the same date over the same set.
- The route is on the existing goal-scoped `APIRouter` in
  `presentation/api/routes/study_plans.py` — the only route in that module that writes nothing.
- The frontend is `features/planner/PlanFeasibility.tsx` with its CSS Module, `readPlanFeasibility` in
  `lib/api-client.ts`, and the types in `types/study-plan.ts`. It renders the backend's sentence
  rather than composing one, and carries no control.
- Covered at four levels: pure domain tests including the equality of the weekday shortcut with a
  day-by-day walk over a six-month horizon; use-case tests against fakes with a fixed clock, including
  that asking twice changes no stored row; API tests over the real application factory, including that
  the path refuses a write method; and PostgreSQL integration tests over the seeded GATE CSE
  curriculum, asserting 60 remaining topics and that no row moves. Frontend tests cover the panel's
  three verdicts, both unknown reasons, the absence of any control, and the absence of a percentage or
  a fraction.
- Open and deliberately not settled here: whether a per-topic time estimate should ever replace the
  one-session assumption; whether a feasibility snapshot should also be stored on a plan for history;
  whether the daily or monthly view should surface this; and whether anything should recompute it when
  availability is saved.
- Recorded as DEC-039 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-013: Model an examination period as a published window of reference data](ADR-013-examination-schedule-and-study-goal.md) — the examination window this measures against
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the envelope and error codes this contract answers in
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology the panel inherits
- [ADR-018: Store weekly availability as named days replaced a week at a time](ADR-018-weekly-availability-slots.md) — the week this totals, and the kept-free distinction the `unknown` verdicts preserve
- [ADR-019: Store planning preferences as typed columns replaced as a group](ADR-019-study-goal-planning-preferences.md) — the session length this consumes, and why an unset one is not a default
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](ADR-020-initial-study-plan-generation.md) — the horizon rule this reuses, and the gap it recorded under *Negative*
- [ADR-022: Adapt a study plan by rebuilding it around what happened](ADR-022-plan-adaptation.md) — the completed-topic exclusion this reuses, and the criterion it narrowed without closing
- [ADR-023: Show today's work as a reading of the weekly plan, not a daily plan](ADR-023-daily-study-view.md) — the sixth-endpoint refusal whose stated condition this change meets
- [ADR-024: Let a learner skip a plan item, settling the item without retiring the topic](ADR-024-plan-item-skipping.md) — why a skipped topic still needs time
- [ADR-025: Let a learner postpone a plan item, settling it while the work waits for the next adaptation](ADR-025-learner-postponement.md) — why a postponed topic still needs time
- [ADR-026: Show the month as a reading of the roadmap and the week, not a monthly plan](ADR-026-monthly-study-view.md) — the frontend-only reading this record deliberately departs from, and why
- [API conventions](../api/conventions.md) — the envelope, the error codes, and the `snake_case` rule
- [API endpoint catalog](../api/endpoints.md) — the contract this record decides
- [API versioning](../api/versioning.md) — what makes a change to it breaking
- [Database schema](../database/schema.md) — the tables this reads and does not alter
- [Domain model](../domain/domain-model.md) — the study goal, availability, and plan this reasons over
- [Terminology](../domain/terminology.md) — *plan feasibility*, the total that belongs to a planner, and the ratio rule
- [Functional requirements](../requirements/functional.md) — FR-004's third criterion, met in full
- [Coding standards](../development/coding-standards.md) — the UI responsibility rule that decided the layer
- [Repository and folder structure](../development/folder-structure.md) — where the rule, the endpoint, and the panel live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 3 item this closes
- [Architecture decision register](../architecture/decisions.md) — DEC-039
