---
title: "ADR-025: Let a Learner Postpone a Plan Item, Settling It While the Work Waits for the Next Adaptation"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-13
related:
  - ../00-project-context.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-017-topic-progress-api-and-schema.md
  - ADR-020-initial-study-plan-generation.md
  - ADR-021-plan-item-completion.md
  - ADR-022-plan-adaptation.md
  - ADR-023-daily-study-view.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-024-plan-item-skipping.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../api/versioning.md
  - ../database/schema.md
  - ../domain/domain-model.md
  - ../domain/entities.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../architecture/decisions.md
---

# ADR-025: Let a Learner Postpone a Plan Item, Settling It While the Work Waits for the Next Adaptation

## Status

Accepted — 2026-08-13. Proposed 2026-08-11.

Accepted once the decision below was verified rather than merely argued. **Nothing in the decision
changed on acceptance**; what was verified is recorded immediately below, and none of it is
outstanding.

**What has been verified.** The whole canonical check set is green: the backend suite with warnings
as errors — **752 passed** — Ruff lint and format, the frontend lint, type check, **406 tests**, and
production build, the `scripts/` checks, and the documentation validator. The **PostgreSQL
integration tests were run locally** against the disposable `learnflow_test` database — **227
passed** — so a learner-written `postponed` is confirmed to pass the real `CHECK` on
`plan_items.status`. The development `learnflow` database was not touched, and was checked afterwards
to confirm it.

**This change has been exercised against the production standalone frontend with a contract-shaped
stub API, with JavaScript disabled**, as ADR-015 through ADR-021 and ADR-023 and ADR-024 each were.
**Sixty-one checks passed.** That run mattered here for the reason it mattered for ADR-024: this
change alters the rendered shape of the control again, from two forms per item to three. The run
enforced "no JavaScript" by never running any — it issued raw HTTP requests and submitted each form as
a scriptless browser does, a native multipart POST to the page's own URL carrying the `$ACTION_*`
fields Next.js renders — so a control that only worked once hydrated could not have passed. See
[Implementation notes](#implementation-notes) for what it demonstrated. **Nothing is recorded here as
unverified.**

This completes [FR-004](../requirements/functional.md#fr-004-plan-adaptation)'s **first** acceptance
criterion — "the learner can mark a planned task as completed, skipped, or postponed" — **in full**.
All three verbs are now things a learner does, through PLN-004, and each is reversible while the
item's plan is active. Three records have said in turn that the third was not; this is the one that
makes it so.

It adds **no endpoint, no column, no table, and no migration**. `plan_items.status` has accepted
`postponed` through the `CHECK` created by `20260806_03`, and PLN-005 has written it since
[ADR-022](ADR-022-plan-adaptation.md); this is the second writer of a value that was already stored,
not a new one.

FR-004's **third** criterion — highlighting trade-offs when time is insufficient — is still not
delivered at all.

**This record reverses a decision three accepted ADRs state by name**, which is why it is an ADR
rather than an endpoint edit. ADR-021 refused `postponed` with a `422`; ADR-022 decided that
adaptation writes it "**on the plan being set aside**", with no path by which a learner could; ADR-024
restated the refusal and listed the gap under *Negative*. Those three, and ADR-023 — whose mirrored
overdue boundary moves with the settled set — each now carry a dated note saying which of their
statements this overtakes. None of them was wrong when written.

## Context

[ADR-024](ADR-024-plan-item-skipping.md) closed with the gap named in its own words, twice. Under
*Negative*: "**A learner still cannot postpone an item themselves.** FR-004's first criterion names
postponing as something they do; here it remains something adaptation does to items whose day passed
… A learner who wants one specific item moved to next week, and nothing else touched, has no way to
say so." And under *Implementation notes*, first in its list of what was "open and deliberately not
settled here": "whether a learner should be able to postpone one item themselves, which FR-004's
first criterion names and neither PLN-004 nor PLN-005 offers."

The reason the refusal held for so long is worth stating exactly, because it has been discharged
rather than overruled. [ADR-021](ADR-021-plan-item-completion.md) refused the status on the ground
that "postponing work raises a question this change cannot answer: postponed *to when?* That is the
re-planning FR-004's second criterion asks for, which is PLN-005 and does not exist." **PLN-005 now
exists.** Adaptation carries postponed work onto the plan that replaces the one it was on, and has
done since ADR-022. The destination the refusal was waiting for is built, and has been for two
records.

What remained was a gap between two vocabularies rather than a missing capability. A learner can say
*this happened* and *this will not happen*; the product can say *this did not happen on its day and
moves to the next plan*. The one thing nobody can say is *this has not happened yet and I mean to do
it* — the ordinary answer to an ordinary Tuesday. A learner who means to return to a session today
has only two words available, and both are wrong: `completed` is untrue, and `skipped` says a
decision they have not made. So they leave it `planned`, and the item reads exactly as it did before
they thought about it.

Six questions had to be answered, and the project owner decided each of them.
[ADR-014](ADR-014-api-response-contract.md) had already fixed the envelope and the error catalogue,
so none of that was open.

1. **What a learner-set `postponed` means, and what the next adaptation does with it.**
2. **Which transitions**, now that `plan_items.status` holds four values and PLN-004 accepted three.
3. **Whether anything records *when* a postponement happened, or *why*.**
4. **Whether an undated roadmap item may be postponed**, given that ADR-022 rules such an item is
   never overdue.
5. **How a postponed item appears** on `/plan`'s two panels and in the daily study view.
6. **The API and frontend topology**, and **whether this needs an ADR**.

### One finding that shaped the answers

**The status already had a writer, and that writer had to be prevented from overwriting the
learner.** `select_overdue` selects unsettled items whose day has passed, and `SETTLED_STATUSES` held
`completed` and `skipped` alone. Had PLN-004 simply accepted `postponed` with nothing else changed, a
learner-postponed item whose day then passed would have been picked up by the next adaptation, marked
`postponed` a second time, and — the part that matters — **reported in `postponed_plan_item_ids`**, so
the sentence the learner reads would have claimed adaptation carried forward work they had already
carried forward themselves.

The stored end state would have been identical, which is what makes this the kind of defect that
ships. It is the same shape as the one ADR-024 found in `is_done`, one status later.

## Decision

### PLN-004 accepts `postponed`, and every move between the four is allowed

`PATCH /api/v1/plan-items/{plan_item_id}` accepts `planned`, `completed`, `skipped`, and `postponed`
as targets, from whichever of them the item currently holds. No endpoint is added, no path changes,
and the request and response shapes are exactly as ADR-021 fixed them.

**Nothing is one-way**, which is the position [ADR-017](ADR-017-topic-progress-api-and-schema.md)
took on a learning stage, ADR-021 on completion, and ADR-024 on skipping. A learner may postpone a
completed item, complete a postponed one, and put either back. Requiring a trip through `planned`
first was rejected below: the four statuses are four answers to one question, not a sequence.

**`PLAN_ITEM_STATUS_CHANGES` now equals `PLAN_ITEM_STATUSES`**, where ADR-021 created it as a strict
subset. The two names are deliberately kept apart rather than collapsed, because they still answer
different questions — what a learner may *ask for*, and what the column may *hold* — and only the
second is mirrored by the `CHECK`. That they coincide today is a fact about the product having run
out of statuses only adaptation writes.

**`completed_at` still travels with `completed` alone.** Postponing a completed item clears it, as
skipping or returning it to `planned` does.

**Postponing names no date.** No request field carries one, and `scheduled_for` is not rewritten. A
learner naming a day would be editing an item's *content* rather than saying what became of its work,
which no endpoint in the plan contract allows and which is a materially larger decision — see
*Alternatives*. Where the work goes is already decided: onto the plan the learner's next adaptation
writes, which is where ADR-022 sends postponed work.

### A learner's postponement is settled, and adaptation leaves it alone

`postponed` joins `SETTLED_STATUSES` beside `completed` and `skipped`. A postponed item is
**never overdue**, so adaptation does not re-mark it, does not report it in
`postponed_plan_item_ids`, and leaves it exactly as the learner left it. Its **topic is planned
again** on the plan that replaces it, because only a `completed` topic is excluded — ADR-022's rule,
unchanged.

The set's meaning widens with it, and the widening is the point rather than an accommodation. It
was "the statuses in which the learner has said what became of an item's work"; it is now "the
statuses in which nothing should carry an item forward on its own". `planned` is the only status
outside it, and it is the only one about which nothing has been said.

**Including the status costs nothing where adaptation wrote it.** An item adaptation marked
`postponed` sits on a plan it superseded in the same operation, and adaptation reads only a goal's
*active* plans — so it never meets one of its own postponements again. The set therefore changes
behaviour for exactly one case: the one this record adds.

`select_overdue`'s fourth boundary becomes a fifth clause in the same sentence rather than a new
rule. The domain function is unchanged; `DatedItem.is_settled` keeps the name ADR-024 gave it, and
the name is what made this a one-word change instead of a rewrite.

### Nothing records when a postponement happened, or why

There is no `postponed_at`, and no migration adds one. This is ADR-024's answer to the same question
about `skipped_at`, for the same reasons: nothing reads it, it would add a second timestamp with its
own invariant against `status` to keep in step in every write path, and `plan_items.status` carries
the whole of what a postponement is. `completed_at` exists because a completion is an event a learner
may later want dated; a postponement is a standing state of an item.

**No reason is collected either.** Asking why a learner postponed would invite the product to form a
view about the answer — the judgement
[FR-005](../requirements/functional.md#fr-005-topic-progress-and-learning-evidence) refuses, and the
one [terminology](../domain/terminology.md) already names as wording to avoid for a skip.

### An undated roadmap item may be postponed

PLN-004 accepts `postponed` on any item whose plan is `active`, roadmap or weekly, and the control
appears on both panels.

Refusing it on an undated item was considered and rejected. The objection is real — postponing reads
as *not on this day*, and a roadmap item names no day, which is why ADR-022 rules such an item is
never overdue. But the endpoint has never known the difference between a dated and an undated item,
and teaching it would put a per-item-shape rule into a contract whose only current rules are
ownership and the plan's state. A roadmap postponement reads as *not this stretch*, which is a thing
a learner may reasonably mean about a topic they have decided to come back to.

### A postponed item stays where it is, marked, and leaves *From earlier days*

`/plan`'s roadmap and week panels and `/plan/today` all show a postponed item **in place**, marked
*Marked postponed* in words, with the controls to complete it, skip it, or put it back. Its day is
not rewritten, so it sits under the date the plan gave it.

**It does not appear under *From earlier days*.** That heading is for work whose day passed and which
is still outstanding; a postponement is the learner having answered. The display partition in
`features/planner/today.ts` mirrors `select_overdue` exactly, as
[ADR-023](ADR-023-daily-study-view.md) established and ADR-024 kept, and the two move together again
here. A screen that called the item outstanding while adaptation refused to carry it forward would
tell the learner two different things about one line.

The mirror is now a named set on both sides — `SETTLED_STATUSES` in the application and
`PLAN_ITEM_SETTLED_STATUSES` in `types/study-plan.ts` — rather than a condition written out in three
places. That does not remove the duplication ADR-023 recorded as a cost; it reduces it to one line
per side, which is the most a frontend that cannot import from the backend can do.

**A status this build does not recognise is still treated as outstanding**, and still shown with no
control. Every value the column holds is now offered, so that path is reached only by a value a later
backend adds — and an unrecognised status must land under *From earlier days* rather than vanish
from it, because the safe reading of "nobody has said anything about this" is that the work is still
owed.

### The control offers three targets, through the existing server action

`PlanItemStatusControl` renders one form per offered target, which is now three rather than two.
No new component, no new action, and no new state shape: `savePlanItemStatus` gains one message and
`PLAN_ITEM_STATUS_CHANGE_LABELS` one entry.

The status still travels in a **hidden field** rather than on the button, so a scriptless submission
carries it exactly as a hydrated one does. The browser still issues no request to the backend, so
`API_CORS_ALLOWED_ORIGINS` stays planned. This inherits
[ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md) through ADR-024 rather than
renegotiating it, and the forms work without JavaScript.

**The confirmation after a postponement says where the work goes and who moves it** — "This work is
placed again when you update your plan." A learner reading "Marked postponed" alone could reasonably
conclude something had already re-dated it, which is exactly what does not happen.

### Nothing adapts, counts, or judges

Postponing an item re-plans nothing. There is no scheduler and no background job, and completing,
skipping, or postponing an item still triggers no adaptation — the learner asks, on `/plan`. That is
ADR-022's accepted decision, and this record leans on it rather than touching it: a postponement is a
note to the next adaptation, not a request for one.

Nothing writes a learning stage. Rule 4 of the
[domain model](../domain/domain-model.md#domain-rules-and-invariants) reads here as it does for a
skip: a plan item records whether planned work happened, so deferring a session says nothing about
how well the learner understands the topic.

Nothing counts postponements — not on a screen, not on a plan, not in an adaptation's reason. A
postponement count would be a number describing the learner rather than the plan, which is the line
[terminology](../domain/terminology.md#plan-coverage-counts-are-not-learner-scores) draws.
`completed_topic_count` and `remaining_topic_count` are unchanged, and a postponed topic counts
toward the second.

## Consequences

### Positive

- **FR-004's first acceptance criterion is met in full**, for the first time. All three verbs are
  learner actions, each reversible, and none of them is a verdict.
- **The learner has a word for the ordinary case.** *I still mean to do this* was the one answer the
  product had no way to record, and its absence pushed learners toward `skipped`, which says
  something they had not decided.
- **No endpoint, no column, no table, no migration.** Nothing stored is reinterpreted, and no
  existing plan, completion, skip, or adaptation-written postponement is touched.
- **A latent defect is closed rather than shipped**, as ADR-024's was: accepting the status without
  the settled rule would have let adaptation report a learner's own postponement as work it carried
  forward.
- **The mirrored overdue rule is now a named set on each side**, so the next status to move it edits
  one line per side rather than three conditions.
- **No new error code was needed**, and no response field was added.

### Negative

- **`postponed` now has two writers and one meaning that has to cover both.** A learner reading a
  superseded plan cannot tell whether they postponed a line or adaptation did. The unified reading —
  *this work did not happen on its day and moves to the next plan* — is true of both, but it is a
  reading rather than a stored distinction, and `postponed_plan_item_ids` is the only place the
  difference survives.
- **Four buttons' worth of decision now sits beside every item**: three controls and a label. The
  roadmap carries sixty items, and ADR-024 already recorded the density of three as a cost. This is
  the second increment, and the panels have still not been factored into a shared item component —
  the refactor ADR-023 declined and ADR-024 declined again.
- **A postponed item is indistinguishable from a skipped one in what the next plan does.** Both are
  settled, both leave the topic in, both are left alone by adaptation. The difference is entirely in
  what the record says, which is a real difference to a learner reading their history and no
  difference at all to the planner.
- **Postponing still moves nothing by itself.** A learner who postpones every item of a week and does
  not adapt has changed four labels and no dates. The screen says so, but the word promises more
  motion than the product performs until they ask for it.
- **The overdue rule's two homes both moved again**, for the second consecutive change. ADR-023
  recorded the duplication as a cost with one test per side; that remains the only thing standing
  between them and a drift.
- **Nothing says when an item was postponed**, so a learner cannot see that they have postponed the
  same session four weeks running. Nothing counts it either, by decision.

### Neutral

- Nothing here totals, counts, ranks, or scores. No postponement count, no percentage, no streak.
- No AI provider is involved, and no configuration variable is read.
- `monthly` and `daily` remain constrained and unwritten, as do `practice`, `revise`, and
  `review_mistakes`.
- The domain layer still holds one module, its rules are still pure, and `select_overdue` and
  `DatedItem` are unchanged in signature and behaviour.
- No command-line tool postpones a plan item.

## Alternatives considered

### Keep `postponed` refused, as ADR-021 decided

Leave the status to adaptation, and let a learner who wants an item moved skip it and adapt.

**Not selected:** the reason for the refusal was that postponing had no destination, and it has had
one since ADR-022. Skipping is not a substitute — it records a decision the learner has not made —
and FR-004's first criterion names postponing as a learner action, which no reading of the current
behaviour satisfies. Four accepted records have now listed the gap; the honest options were to close
it or to amend the requirement.

### Postpone to a date the learner names

`{"status": "postponed", "scheduled_for": "2026-08-18"}`, rewriting the item's day on the active
plan.

**Not selected**, and this is the largest of the alternatives rather than a variant. It would make an
item's *content* learner-writable for the first time — every other write in the plan contract moves
a status — and would raise a set of questions this change does not answer: whether a learner may date
work outside the plan's period, what happens to the day's capacity, whether the placement rules still
describe the plan afterwards, and what `recommendation_reason` means once it explains a day nobody
planned. ADR-020's guarantee that a plan is deterministic from stored inputs would hold only until
the first hand-placed item. If manual re-dating is wanted later, it is its own decision with its own
record.

### Postponed stays unsettled, and adaptation claims it

Leave `SETTLED_STATUSES` alone and have adaptation treat a learner-postponed item as work it carries
forward, reporting it in `postponed_plan_item_ids` whatever its date.

**Not selected:** the stored outcome is identical — the topic is re-planned either way — so the only
thing it changes is the sentence the learner reads, and it makes that sentence less true. Adaptation
would claim to have carried forward work the learner had already dealt with, and a postponement of an
item dated *next Friday* would be reported as though a day had passed. It would also need
`select_overdue` to grow a clause that is not about dates, in a function whose whole subject is
dates.

### Postpone reachable only from `planned`

A completed or skipped item would have to be returned to `planned` first.

**Not selected:** it is a two-step undo for a mis-tap and invents an ordering the data has no reason
to hold — the objection ADR-024 raised against the same shape for skipping. The four statuses are
four answers to one question.

### Refuse `postponed` on an undated roadmap item

A `422` naming the item's shape, on the ground that postponing means *not on this day*.

**Not selected:** it adds a per-item-shape rule to a contract that has none, and a new refusal to
document, for a case where the learner's meaning is clear enough. See the decision above.

### Add `postponed_at`

A nullable `timestamptz`, additive, so history says when an item was postponed.

**Not selected:** ADR-024's reasoning about `skipped_at`, unchanged. Nothing reads it; it would add a
second timestamp with its own invariant against `status`; and it stays an additive migration
available later if something ever needs the date.

### A dedicated `POST /plan-items/{id}/postpone`

An action endpoint rather than a status target.

**Not selected:** the objection ADR-021 and ADR-024 both raised. Undoing would need a second path, at
which point the `PATCH` is doing the work anyway — and PLN-004 is the catalogued contract for exactly
this.

## Implementation notes

- Endpoint fields and per-endpoint error codes are in
  [api/endpoints.md](../api/endpoints.md#pln-004-patch-apiv1plan-itemsplan_item_id), which stays
  authoritative.
- **No migration.** `plan_items.status` has accepted `postponed` through the `CHECK` created by
  `20260806_03`, and PLN-005 has written it since ADR-022. This change adds a second writer of an
  existing value.
- `PLAN_ITEM_STATUS_CHANGES` becomes `PLAN_ITEM_STATUSES` in
  `application/dto/study_plan.py`, and `POSTPONED` joins `SETTLED_STATUSES` there. The two
  status tuples stay separately named, for the reason the *Decision* gives.
- `backend/app/domain/study_planning.py` is unchanged apart from its docstrings: `select_overdue`
  reads `is_settled`, and which statuses are settled is an application fact. That the domain needed
  no edit is the return on ADR-024's rename.
- `ManageStudyPlans.record_item_status` is unchanged in structure. Its status check admits a fourth
  value, and the `422` message no longer explains where postponing comes from, because it no longer
  comes from anywhere else.
- The frontend is `features/planner/PlanItemStatusControl.tsx`, unchanged in shape — it already
  renders one form per offered target. `PLAN_ITEM_SETTLED_STATUSES` and `isSettledStatus` join
  `types/study-plan.ts`, and `plan.ts`'s `itemClassName` and `today.ts`'s `isOutstanding` both read
  them, so the frontend's copy of the settled set is written once.
- Covered at four levels: the pure domain test for the settled boundary, use-case tests against fakes
  with a fixed clock — including the four-status walk and the assertion that adaptation neither
  re-marks nor reports a learner's postponement — API tests over the real application factory for
  both PLN-004 and PLN-005, and PostgreSQL integration tests writing `postponed` from PLN-004 against
  the real `CHECK`. On the frontend, the panel and daily-view tests assert the control on all three
  screens, that a postponed item keeps its place, its day, and its reason, that it leaves *From
  earlier days*, that an unrecognised status does not, and that nothing is counted.
- **The scriptless standalone-frontend run was performed**, against a contract-shaped stub API with
  the server on `TZ=UTC`. **Sixty-one checks passed.**

  Verified on `/plan`: a planned item offers exactly three forms — *Mark completed*, *Skip this item*,
  and *Postpone this item* — each carrying `method="POST"`, `encType="multipart/form-data"`, an empty
  `action`, and the status it will set **in a hidden field** rather than on the button; a completed
  item offers *Return to planned*, *Skip this item*, and *Postpone this item*; a skipped item offers
  *Mark completed*, *Return to planned*, and *Postpone this item*; a **postponed** item offers the
  other three and **no postpone**; an **undated roadmap item offers the postpone control too**; and an
  item in a status this build does not recognise gets **no control at all** and is reported in words.

  **A no-JavaScript postponement reached PLN-004 exactly once**, at `/api/v1/plan-items/{id}` with the
  body `{"status":"postponed"}` and nothing else — **no date was sent**; **only that item moved**, one
  further *Marked postponed* label rendering while every other item kept its own controls; the
  postponed item kept its place, its day, its reason, and its topic name; the postponement was undone
  with one `{"status":"planned"}` write; and completing and skipping still made exactly one
  `{"status":"completed"}` and one `{"status":"skipped"}` write with their own confirmations.

  On `/plan/today`: **the learner's own date, never the server's** — the same plan rendered under
  `Pacific/Kiritimati` and `Pacific/Midway` produced two different dates; today's planned and
  completed items both rendered with their reasons and controls; the outstanding item from a day that
  had passed appeared under *From earlier days*; **the postponed item from that day did not appear
  there at all**, nor did the skipped one, which is the display half of the settled rule; a day still
  to come was absent; a postponement made from this screen reached PLN-004 once and the item stayed on
  today, marked; the screen offered **no generate and no adapt control**; and no count, percentage, or
  copy describing the learner appeared.

  Also verified: an item on a **superseded plan was refused**, the stub answering `409`, with the
  learner shown the action's own wording; **adaptation** posted once to the goal-scoped
  `/api/v1/study-goals/{id}/adapt` with no caller-supplied field and reported the one outstanding
  overdue item as carried forward and **neither the skipped nor the postponed one**; **nothing adapted
  on its own** during any read; and **no API address appeared** in the HTML of `/plan`,
  `/plan/today`, `/`, `/setup`, or `/curriculum`, nor in any of the thirteen client scripts they load.

  **Three assertions failed on the first runs and all three were defects in the harness, not the
  product** — the same pattern ADR-021 and ADR-024 recorded. The harness submitted the `$ACTION_*`
  fields with their HTML entities still encoded, which a browser decodes and which Next.js answers
  with a `500`. The adapt-form selector matched on button text that had been guessed rather than read,
  so it found nothing; selecting on the component's CSS-module class fixed it, which is exactly the
  fix ADR-024's run needed for the same form. And the stub's fixture dates were absolute, so the run
  stopped meaning *today* the moment it crossed a UTC midnight; making them relative to the day of the
  run settled it.
- **`npm test` passes in its canonical form.** An earlier run of it on this workstation failed to
  start Vitest workers for seven of the twenty-nine test files — a `[vitest-pool]: Failed to start
  forks worker` timeout, never a failing assertion. It was investigated rather than assumed
  environmental and **could not be reproduced**: four subsequent canonical runs passed, including one
  with the Vite transform cache cleared and one under deliberate concurrent CPU load. The affected
  files included ones this change does not touch, such as `CurriculumTree.test.tsx`, and the set
  differed between the two failing runs, so it was neither file-specific nor caused by this change.
  No Vitest configuration, test, dependency, or script was changed. CI remains the canonical Linux
  verification.
- Open and deliberately not settled here: whether a learner should be able to re-date an item
  themselves, and where that would live; whether a superseded plan should distinguish a learner's
  postponement from adaptation's; whether repeated postponements of one item should be visible
  anywhere; whether a learner should ever be able to remove a topic from a goal durably; and how a
  plan should report that a week cannot reach its horizon, which is FR-004's remaining criterion.
- Recorded as DEC-037 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](ADR-011-sqlalchemy-persistence-implementation.md) — the validated-text rule that keeps the `CHECK` and the endpoint separate, and the note recording that they now agree
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the envelope and error codes this contract answers in
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology this control inherits
- [ADR-017: Record manual topic progress as a learner-owned stage](ADR-017-topic-progress-api-and-schema.md) — the any-to-any reversibility this follows, and the stage this change refuses to write
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](ADR-020-initial-study-plan-generation.md) — the plan this acts on, and the `status` column it completes as a learner contract
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](ADR-021-plan-item-completion.md) — the contract this extends, and the `422` this lifts
- [ADR-022: Adapt a study plan by rebuilding it around what happened](ADR-022-plan-adaptation.md) — where postponed work goes, and the other writer of the status
- [ADR-023: Show today's work as a reading of the weekly plan, not a daily plan](ADR-023-daily-study-view.md) — the display partition that mirrors the changed set
- [ADR-024: Let a learner skip a plan item, settling the item without retiring the topic](ADR-024-plan-item-skipping.md) — the record that named this gap, and the `is_settled` rename that made closing it a one-word change
- [API conventions](../api/conventions.md) — the envelope, the error codes, and the `snake_case` rule
- [API endpoint catalog](../api/endpoints.md) — the contract this record extends
- [API versioning](../api/versioning.md) — why accepting a further request value is compatible
- [Database schema](../database/schema.md) — `plan_items.status`, and its second writer
- [Domain model](../domain/domain-model.md) — rule 4, which this record applies again
- [Domain entities](../domain/entities.md) — the plan item whose status this moves
- [Terminology](../domain/terminology.md) — *postponed*, and how it now differs from *skipped*
- [Functional requirements](../requirements/functional.md) — FR-004's first criterion, met in full
- [Repository and folder structure](../development/folder-structure.md) — where the rule and the planner feature live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 3 item this closes
- [Architecture decision register](../architecture/decisions.md) — DEC-037
