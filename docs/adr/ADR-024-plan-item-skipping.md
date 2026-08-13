---
title: "ADR-024: Let a Learner Skip a Plan Item, Settling the Item Without Retiring the Topic"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-11
related:
  - ../00-project-context.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-017-topic-progress-api-and-schema.md
  - ADR-020-initial-study-plan-generation.md
  - ADR-021-plan-item-completion.md
  - ADR-022-plan-adaptation.md
  - ADR-023-daily-study-view.md
  - ADR-025-learner-postponement.md
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

# ADR-024: Let a Learner Skip a Plan Item, Settling the Item Without Retiring the Topic

## Status

Accepted — 2026-08-11. Proposed 2026-08-10.

Accepted once the decision below was verified rather than merely argued, and once CI had run the same
checks against an ephemeral database. **Nothing in the decision changed on acceptance.**

**What has been verified.** The whole canonical check set is green: the backend suite with warnings as
errors, Ruff lint and format, the frontend lint, type check, 384 tests, and production build, the
`scripts/` checks, and the documentation validator. The **PostgreSQL integration tests were run
locally** against a disposable `learnflow_test` database — 224 passed — so `skipped` is confirmed to
pass the real `CHECK` on `plan_items.status`. No learner data was touched. **CI then ran all five
jobs green** on pull request #25, its `database` job reporting the same 224 passed against a
`postgres:18-alpine` service container.

**This change has been exercised against the production standalone frontend with a contract-shaped
stub API, with JavaScript disabled**, as ADR-015 through ADR-021 and ADR-023 each were. **Fifty-nine
checks passed.** That run mattered more here than for most changes, because this one alters the
rendered shape of the control: `PlanItemStatusControl` now renders one `<form>` per offered target
rather than one form in total. The run enforced "no JavaScript" by never running any — it issued raw
HTTP requests and submitted each form as a scriptless browser does, a native multipart POST to the
page's own URL carrying the `$ACTION_*` fields Next.js renders — so a control that only worked once
hydrated could not have passed. See [Implementation notes](#implementation-notes) for what it
demonstrated. **Nothing is recorded here as unverified.**

This takes [FR-004](../requirements/functional.md#fr-004-plan-adaptation)'s **first** acceptance
criterion — "the learner can mark a planned task as completed, skipped, or postponed" — as far as it
goes today, and **does not meet it in full**. Stated precisely:

- **A learner can explicitly mark a plan item `completed` or `skipped`**, and take either back.
  Those two are learner actions, through PLN-004.
- **A learner cannot mark an item `postponed`.** Adaptation writes that status, on the plan it
  supersedes, for items whose day passed with the work still `planned`
  ([ADR-022](ADR-022-plan-adaptation.md)). The learner asks for adaptation; they do not choose which
  items it postpones, and PLN-004 refuses `postponed` with a `422`.

So two of the criterion's three verbs are things the learner does, and the third is a consequence of
something else they ask for. Whether that satisfies the criterion as written is the project owner's
call, and this record does not claim it does.

`skipped` was the last of the four `plan_items.status` values nothing wrote; **all four are now
written**, which is a statement about the column rather than about the criterion. It adds **no
endpoint, no column, no table, and no migration**.

FR-004's **third** criterion — highlighting trade-offs when time is insufficient — is not delivered
at all.

## Implementation status — 2026-08-11

*Note added 2026-08-11. The decision below is unchanged in everything but the set of statuses PLN-004
accepts and the set `select_overdue` reads; this records what has been overtaken and by what.*

**A learner can postpone an item.** [ADR-025](ADR-025-learner-postponement.md) extends PLN-004 to
accept `postponed` as a fourth target, so a learner may now move an item between all four statuses in
any direction. It needed **no migration** either, and the status already had a writer — this is its
second.

**Six statements above are overtaken.** None was wrong when written.

- In the [Status](#status) section — "**A learner cannot mark an item `postponed`** … PLN-004
  refuses `postponed` with a `422`", and the conclusion that FR-004's first criterion is "**partly**
  met, not met in full". They can, and it is now met **in full**: all three verbs are learner
  actions. The `422` remains only for a status the column could not hold either.
- The same section's "two of the criterion's three verbs are things the learner does, and the third
  is a consequence of something else they ask for". All three are things the learner does. Adaptation
  still writes `postponed` for work whose day passed with nothing said about it, so the status has
  two writers rather than one.
- Under [Decision](#pln-004-accepts-skipped-and-every-move-between-the-three-is-allowed) —
  "**`postponed` is still refused, with a `422`.** Its reason has narrowed rather than changed."
  The reason has now been discharged: ADR-021 refused the status because postponing had no
  destination, and PLN-005 has been that destination since ADR-022.
- The same section's `PLAN_ITEM_STATUS_CHANGES` of `("planned", "completed", "skipped")` is now the
  whole of `PLAN_ITEM_STATUSES`. The two constants stay separately named for the reason this record
  gives; they simply coincide today.
- Under [Decision](#the-write-goes-through-the-existing-server-action-and-the-backend-gains-no-cors)
  — "**An item in a status the API will not take as a target gets no control at all.** That means
  `postponed`, and only `postponed`". It now means no stored status at all; the branch is reached
  only by a value a later backend adds. `PlanItemStatusControl` renders **three** forms rather than
  two.
- Under [Consequences](#negative) — "**A learner still cannot postpone an item themselves.** … A
  learner who wants one specific item moved to next week, and nothing else touched, has no way to say
  so." They have one. Note that postponing still moves nothing on its own: it settles the item, and
  the work is placed again when the learner adapts.

**The `is_settled` rename is what made that a one-word change.** `POSTPONED` joins
`SETTLED_STATUSES` and the domain function is untouched — the fourth boundary this record added
became a fifth clause in the same sentence. The rule and its display mirror moved together again,
which is the second time the cost ADR-023 recorded has been paid.

**A postponed item behaves on every screen as a skipped one does**: in place, marked in words, with
the controls to move it, and **left out of *From earlier days***. What separates the two is what the
record says about the line — *not happening* against *not happening yet* — and nothing about what the
next plan does with the topic, which is the same for both.

**Everything else in this record stands.** The reversibility argument, the `409` for an item on a
superseded plan, the refusal to write a learning stage, the refusal to count anything, the absence of
a timestamp and of a reason field, and the topic-not-retired rule are all as accepted, and ADR-025
inherits each rather than renegotiating it.

## Context

Three accepted records left this open by name, and each said so in the same words.

[ADR-021](ADR-021-plan-item-completion.md) refused `skipped` alongside `postponed` and recorded why:
"Skipping is closer to viable, but it belongs with the same re-planning question: a plan that knows
work was skipped and does nothing about it is not obviously better than one that does not know." It
listed under *Negative* that "**`skipped` remains unwritten**, so a learner who wants to abandon a
topic still cannot say so."

[ADR-022](ADR-022-plan-adaptation.md) built the re-planning that answer depended on, and stopped
deliberately at the same line: "`skipped` stays unwritten. Nothing yet lets a learner abandon a topic
outright, and inventing that alongside adaptation would be two features in one change." Its open
questions name "when `skipped` arrives and what it means for adaptation".

[ADR-023](ADR-023-daily-study-view.md) listed `skipped` among the values that "remain constrained and
unwritten, exactly as ADR-020 and ADR-022 left them".

So a learner today has two things they can say about a planned session — it happened, or nothing —
and one thing the product says for them, `postponed`, when a day passes. What they cannot say is
*this is not happening*. The plan then carries that session forward on every adaptation, for as long
as the learner keeps declining to do it, and the learner has no way to stop being asked.

Seven questions had to be answered, and the project owner decided each of them.
[ADR-014](ADR-014-api-response-contract.md) had already fixed the envelope and the error catalogue, so
none of that was open.

1. **Which transitions**, given `plan_items.status` holds four values and PLN-004 accepted two.
2. **Whether a skipped item still appears** on the plan screens and in the daily study view.
3. **What a skip does to a later adaptation** — the question ADR-022 left by name.
4. **Whether a skip on a superseded plan may be taken back.**
5. **The API and frontend topology.**
6. **Whether anything records *when* a skip happened.**
7. **Whether this needs an ADR**, given both the endpoint and the status value were catalogued.

### One finding that shaped the answers

**A latent defect made question 3 urgent rather than optional.** `select_overdue` in
`backend/app/domain/study_planning.py` decided *behind* from a field named `is_done`, which the use
case filled with `status == 'completed'`. Had `skipped` simply been accepted by PLN-004 with nothing
else changed, the first adaptation after a skipped item's day passed would have overwritten it with
`postponed` — replacing the learner's own statement with an inference about a date, on the plan being
set aside, where PLN-004 then refuses to let them put it back. The status would have been writable
and not durable.

The rest was already in place: the `CHECK` on `plan_items.status` has accepted `skipped` since
`20260806_03`, and PLN-004 already existed. **This change therefore adds no column, no table, and no
migration**, and no existing record is reinterpreted.

## Decision

### PLN-004 accepts `skipped`, and every move between the three is allowed

`PATCH /api/v1/plan-items/{plan_item_id}` accepts `planned`, `completed`, and `skipped` as targets,
from whichever of them the item currently holds. No endpoint is added and no path changes; the
request and response shapes are exactly as ADR-021 fixed them.

**Nothing is one-way.** A learner may skip a completed item, complete a skipped one, and put either
back to `planned`. That is the position [ADR-017](ADR-017-topic-progress-api-and-schema.md) took on a
learning stage — "a learner may move to any stage from any stage, including backwards" — and the one
ADR-021 took on completion. A control that a mis-tap makes permanent, on a list of sixty items, is
the only kind of control LearnFlow has consistently refused.

**`postponed` is still refused, with a `422`.** Its reason has narrowed rather than changed:
adaptation writes it as it sets a plan aside, so asking for it here would set a status with nothing to
move the work *to*. The message now says where postponing comes from instead of saying it is not
built.

**`completed_at` still travels with `completed` alone.** Skipping a completed item clears it, as
returning one to `planned` does. An item is completed at an instant or it is not completed at all.

### Skipping settles the item; it does not retire the topic

A skipped item is **never overdue**. Adaptation leaves it exactly as the learner left it, and its
**topic is planned again** on the plan that replaces it.

This is the answer to ADR-022's open question, and it deliberately differs from what a completion
does. The two statuses answer different questions:

- **Completed** says *the work is done*, so the topic is excluded from every plan that follows —
  ADR-022's rule, unchanged.
- **Skipped** says *the work is not happening now*, so the topic returns. A learner who wants it gone
  from the next plan skips it again, which costs one press and is a decision they keep making rather
  than one they made once.

**Retiring the topic was rejected**, under *Alternatives*, on a specific and checkable ground: a skip
survives only until the plan it sits on is superseded, after which PLN-004 refuses to write to it with
a `409`. A skip that also removed the topic would therefore be **irreversible in practice** the moment
the learner adapted — the topic would vanish from planning with no way back, in a product where
nothing else is one-way and where [ADR-022](ADR-022-plan-adaptation.md) already recorded never
planning a completed topic again as a *negative*.

**What counts as settled is a domain rule.** `DatedItem.is_done` becomes `is_settled`, and
`select_overdue` gains a fourth stated boundary beside its three:

- An item dated **today** is not overdue.
- An **undated** roadmap item is never overdue.
- **Completed** work is never overdue, however late it was done.
- **Skipped** work is never overdue, because the learner has already said it is not going to fill
  that day.

The rename is the point rather than tidying: `is_done` was a name that could only ever mean
completion, and the rule it serves is about whether the learner has spoken, not about whether work
occurred.

### A skipped item stays where it is, on every screen

`/plan`'s roadmap and week panels and `/plan/today` all show a skipped item **in place**, marked
*Marked skipped* in words, with the controls to complete it or put it back.

Hiding it was rejected for the reason ADR-021 gave for keeping a completed item visible — the plan is
the record of what was planned, and a roadmap short of a topic misstates it — and for one more that
applies only to skipping: hiding a skip hides a decision the learner may want to take back, on the
only screen offering the control to take it back.

**A skipped item does not appear under *From earlier days*.** That heading is for work whose day
passed and which is still outstanding; a skip is the learner having answered. Showing it there would
ask a question they have already answered, and would disagree with the adaptation that will not
postpone it. The display partition in `features/planner/today.ts` mirrors `select_overdue` exactly as
[ADR-023](ADR-023-daily-study-view.md) established, and moves with it.

### A skip on a superseded plan cannot be changed

Unchanged from ADR-021: only an item whose plan is `active` may be moved, and one on a superseded
plan is refused with `409` `conflict`, whatever status is asked for.

The rule is about the plan's state rather than the item's, so skipping needs no exception and gets
none. A superseded plan is kept **because** it reads exactly as it was written; a narrow "un-skip
only" exception would write into the one record whose worth is that it does not change, and would
make one status behave unlike the other three. The learner is not trapped by this, because the topic
comes back on the new plan.

### The write goes through the existing server action, and the backend gains no CORS

`PlanItemStatusControl` offers the **two statuses the item is not already in**, as two forms posting
to the same `savePlanItemStatus` `"use server"` module. No new component, no new action, no new state
shape.

The status travels in a **hidden field** rather than on the button, so a scriptless submission carries
it exactly as a hydrated one does and neither path depends on submit-button semantics. The browser
still issues no request to the backend, so `API_CORS_ALLOWED_ORIGINS` stays planned. This inherits
[ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md) through ADR-021 rather than
renegotiating it, and the forms work without JavaScript.

**The confirmation after a skip says the topic comes back.** A learner reading "Marked skipped" alone
could reasonably conclude they had dropped the topic for good, which is not what this does.

**An item in a status the API will not take as a target gets no control at all.** That means
`postponed`, and only `postponed`, now that `skipped` is accepted: the status is shown as the API sent
it, in words, rather than presented as something a learner can move. This restates ADR-021's rule with
its set narrowed to one value, because the sentence that carried it grouped `skipped` with `postponed`
and half of it has stopped being true. A `postponed` item reaches a screen only on a superseded plan,
where PLN-004 refuses every write anyway, so the control and the backend agree.

### Nothing records when a skip happened

There is no `skipped_at`, and no migration adds one. `plan_items.status` carries the whole of what a
skip is, exactly as it carries the whole of what a postponement is.

A second timestamp would need its own invariant against `status`, kept in step in every path that
writes one — and nothing reads it. `completed_at` exists because a completion is an event a learner
may later want dated; a skip is a standing state of an item, and the plan's question is what became of
the work rather than at what hour the learner said so.

**No reason is collected either.** Nothing stores why an item was skipped, and asking would invite
the product to form a view about the answer — the judgement
[FR-005](../requirements/functional.md#fr-005-topic-progress-and-learning-evidence) refuses.

### No learning stage, no count, no re-plan

Skipping writes nothing to `learner_topic_progress`. Rule 4 of the
[domain model](../domain/domain-model.md#domain-rules-and-invariants) reads in both directions: a plan
item records whether planned work happened, so declining a session is no more a statement that a
topic is not understood than completing one is that it is.

Nothing counts skips — not on a screen, not on a plan, not in an adaptation's reason. A skip count
would be a number describing the learner rather than the plan, which is the line
[terminology](../domain/terminology.md#plan-coverage-counts-are-not-learner-scores) draws.
`completed_topic_count` and `remaining_topic_count` are unchanged and a skip moves neither, because a
skipped topic is still in the plan.

Nothing re-plans. Skipping an item adapts nothing, exactly as completing one does not — the learner
asks, on `/plan`.

## Consequences

### Positive

- **Two of FR-004's first criterion's three verbs are now learner actions** — completing and
  skipping — where one was before. Postponing stays a consequence of adaptation rather than something
  a learner can ask for, so the criterion is **not** met in full; see [Status](#status).
- **`plan_items.status` has no unwritten value left.** That is a statement about the column, and it
  is true: `planned` on generation, `completed` and `skipped` from PLN-004, `postponed` from PLN-005.
- **The learner can stop being asked.** A session they are not going to do is a thing they can say
  rather than a line they keep scrolling past, and the plan stops presenting it as outstanding.
- **A latent defect is closed rather than shipped.** Accepting `skipped` without the `is_settled`
  rule would have let adaptation overwrite the learner's statement with `postponed` on a plan they
  could no longer write to.
- **No endpoint, no column, no table, no migration.** Nothing stored is reinterpreted and no existing
  plan, completion, or postponed item is touched.
- **`postponed`, `completed`, and `skipped` now mean three visibly different things**, and the
  history of a plan says which happened to every line.
- **No new error code was needed**, and no response field was added.
- **The domain rule got a truer name.** `is_settled` says what the rule actually asks, where `is_done`
  described one of its two answers.

### Negative

- **A learner still cannot postpone an item themselves.** FR-004's first criterion names postponing
  as something they do; here it remains something adaptation does to items whose day passed, and
  PLN-004 refuses the status with a `422`. A learner who wants one specific item moved to next week,
  and nothing else touched, has no way to say so.
- **A skipped topic comes back.** A learner who wants a topic out of their plan permanently has no way
  to say so, and must skip it again after each adaptation. That is the deliberate trade for
  reversibility, and it is the decision most likely to be revisited — see *Open questions*.
- **Three buttons' worth of decision now sits beside every item.** The plan screens carry sixty
  items, each with two controls; the roadmap in particular is longer to read than it was.
- **The overdue rule's two homes both moved.** ADR-023 recorded the domain rule and the display
  partition as a duplication with only one test that would fail if the other drifted; this change
  edited both, which is the first time that cost has actually been paid.
- **`select_overdue`'s field rename touches an accepted record's vocabulary.** ADR-022 describes the
  third boundary as "Completed work is never overdue". That sentence is now one of two, and ADR-022
  carries a dated note saying so rather than being rewritten.
- **Nothing says when an item was skipped**, so a learner cannot see that they skipped the same
  topic four weeks running. Nothing counts it either, by decision.

### Neutral

- Nothing here totals, counts, ranks, or scores. No skip count, no percentage, no streak.
- No AI provider is involved, and no configuration variable is read.
- `monthly` and `daily` remain constrained and unwritten, as do `practice`, `revise`, and
  `review_mistakes`.
- The domain layer still holds one module, and its rules are still pure.
- No command-line tool skips a plan item.

## Alternatives considered

### Skipping retires the topic, as completing does

A skipped topic is excluded from every plan that follows, matching how ADR-021 and ADR-022 describe
the word — "abandon a topic outright".

**Not selected:** it would be irreversible in practice. A skip lives on the plan it was made on; once
the learner adapts, that plan is superseded and PLN-004 refuses to write to it with a `409`. The topic
would then be absent from every future plan with no way to bring it back, which is a one-way door in
a product that has refused every other one. The wording in the earlier records described a capability
nobody had yet designed the lifecycle for; this record designs it, and the lifecycle argues the other
way. If a durable "not for this goal" is wanted later, it belongs on the goal or the topic rather than
on one line of one plan that is about to be replaced.

### One-way `planned → skipped`

The strictest reading of a decision to abandon work.

**Not selected:** nothing in LearnFlow is one-way. A learning stage moves backwards deliberately
(ADR-017) and a completion is reversible (ADR-021), for the same reason each time — a mis-tap on a
long list must not be permanent, and a product that formed an opinion about a mis-tap would be forming
one about the learner.

### Skipping reachable only from `planned`

A completed item would have to be returned to `planned` before it could be skipped.

**Not selected:** it is a two-step undo for a mis-tap, and it invents an ordering the data has no
reason to hold. The three statuses are three answers to one question, not a sequence.

### Leave `select_overdue` alone

Accept `skipped` and let adaptation treat a skipped item whose day passed as overdue.

**Not selected:** it would overwrite the learner's statement with `postponed`, on the plan being set
aside, where they can no longer change it back. The status would be writable and not durable, which is
worse than not offering it.

### Hide skipped items

Drop them from the panels and the daily view, so the plan shows only live work.

**Not selected:** the plan is the record of what was planned (ADR-021), and hiding a skip also hides
the only control that takes it back. A learner who skipped the wrong line would have no way to find
it.

### Show skipped items under *From earlier days*

Keep the display partition as `status !== 'completed'`, so a skipped item whose day passed still
appears as work outstanding.

**Not selected:** it would ask a question the learner has answered, and would disagree with the
adaptation that will not postpone it — the two would tell the learner different things about the same
item.

### Add `skipped_at`

A nullable `timestamptz`, additive, so history says when an item was skipped.

**Not selected:** nothing reads it. It would add a second timestamp with its own invariant against
`status` to keep in step in every write path, for a fact no screen shows and no rule consults.
`plan_items.status` already carries what a skip is. It stays an additive migration available later, if
something ever needs the date.

### `POST /plan-items/{id}/skip`

A dedicated action endpoint.

**Not selected:** the same objection ADR-021 raised. Undoing would need a second path, at which point
the `PATCH` is doing the work anyway — and PLN-004 is the catalogued contract for exactly this.

## Implementation notes

- Endpoint fields and per-endpoint error codes are in
  [api/endpoints.md](../api/endpoints.md#pln-004-patch-apiv1plan-itemsplan_item_id), which stays
  authoritative.
- **No migration.** `plan_items.status` has accepted `skipped` through the `CHECK` created by
  `20260806_03`; this is the first code to write it, and the last of that constraint's four values to
  be written.
- `SKIPPED` and `SETTLED_STATUSES` join the constants in `application/dto/study_plan.py`.
  `PLAN_ITEM_STATUS_CHANGES` becomes `("planned", "completed", "skipped")` and stays deliberately
  separate from `PLAN_ITEM_STATUSES`: one is what a learner may *ask for*, the other what the column
  may *hold*.
- `DatedItem.is_done` is renamed `is_settled` in `backend/app/domain/study_planning.py`, and
  `select_overdue`'s docstring states the fourth boundary. The rule stays pure and clock-free.
- `ManageStudyPlans.record_item_status` is unchanged in structure: the status check it already
  performed now admits a third value, and `_postpone_overdue` reads `SETTLED_STATUSES`. `_listed`
  writes the accepted statuses as a learner reads a list of them.
- The frontend is `features/planner/PlanItemStatusControl.tsx`, which now renders one form per
  offered target; `PLAN_ITEM_STATUS_CHANGE_LABELS` and `PLAN_ITEM_SETTLED_LABELS` live in
  `types/study-plan.ts` beside `PLAN_ITEM_STATUS_CHANGES`. `describeSettledStatus` joins
  `features/planner/plan.ts` so the three panels say *Marked skipped* without a fourth copy of the
  wording; extracting a shared item component from those panels remains the refactor ADR-023
  declined.
- `features/planner/today.ts`'s `isOutstanding` mirrors `is_settled`, which is the display side of
  the same boundary.
- Covered at four levels: a pure domain test for the settled boundary, use-case tests against fakes
  with a fixed clock, API tests over the real application factory for both PLN-004 and PLN-005, and
  PostgreSQL integration tests writing `skipped` against the real `CHECK`. On the frontend, the panel
  and daily-view component tests assert the control on all three screens, that a skipped item keeps
  its place and its reason, that a skipped item leaves *From earlier days*, and that nothing is
  counted.
- **The scriptless standalone-frontend run was performed**, against a contract-shaped stub API with
  the server on `TZ=UTC`. **Fifty-nine checks passed.**

  Verified: a planned item offers exactly two forms, *Mark completed* and *Skip this item*, each
  carrying `method="POST"`, `encType="multipart/form-data"`, an empty `action`, and the status it will
  set **in a hidden field** rather than on the button; a completed item offers *Return to planned* and
  *Skip this item* and no third; a skipped item offers *Mark completed* and *Return to planned* and no
  skip; **a no-JavaScript skip reached PLN-004 exactly once**, at `/api/v1/plan-items/{id}` with the
  body `{"status":"skipped"}` and nothing else; **only that item moved**, one *Marked skipped* label
  rendering while the other items kept their statuses; the skip was undone with one `{"status":
  "planned"}` write and completion still made one `{"status":"completed"}` write; a skipped item kept
  its place, its reason, and its topic name on both `/plan` panels.

  On `/plan/today`: **the learner's own date, never the server's** — the same plan rendered under
  `Pacific/Kiritimati` and `Pacific/Midway` produced two different dates, each the zone's own; today's
  planned and completed items both rendered with their reasons and controls; the outstanding item from
  a day that had passed appeared under *From earlier days* headed by its own date, with the skip
  control beside it; **the skipped item from a passed day did not appear there at all**, which is the
  display half of the settled rule; a day still to come was absent; no percentage or completion count
  appeared, and no copy described the learner rather than an item.

  Also verified: an item on a **superseded plan was refused**, the stub answering `409`, with the
  learner shown the action's own wording rather than the backend's, and the item unchanged;
  **adaptation** posted once to the goal-scoped `/api/v1/study-goals/{id}/adapt` with no
  caller-supplied field, reported the one overdue *planned* item as carried forward and **not** the
  skipped one, and said the previous plan is kept; **nothing adapted on its own** during any read; and
  **no API address appeared** in the HTML of `/plan`, `/plan/today`, `/`, `/setup`, or `/curriculum`,
  nor in any of the thirteen client scripts they load.

  **Two assertions failed on the first run and both were defects in the harness, not the product** —
  the same pattern ADR-021 recorded. The timezone check compared the learner's date with the server's
  own, which happens to agree for most of any day and did; rendering under two fixed zones settled it.
  And the adapt-form selector matched on `study_goal_id`, which the *generate* form also carries, so
  it submitted PLN-001 and every downstream adaptation assertion failed with it; selecting on the
  component's CSS-module class fixed it.

  **One pre-existing discrepancy was found and is not fixed here**, because it is outside this
  change: `adaptStudyPlan` in `lib/api-client.ts` sends `{}` as the request body to PLN-005, which
  [endpoints.md](../api/endpoints.md#pln-005-post-apiv1study-goalsstudy_goal_idadapt) describes as
  taking **no request body**. FastAPI ignores it because the route declares no body parameter, so
  nothing fails, and no caller-supplied field reaches the endpoint — the guarantee that matters. It
  dates from [ADR-022](ADR-022-plan-adaptation.md) and this change does not touch that function.
- Open and deliberately not settled here: whether a learner should be able to postpone one item
  themselves, which FR-004's first criterion names and neither PLN-004 nor PLN-005 offers; whether a
  learner should ever be able to remove a topic
  from a goal durably, and where that would live if so; whether a skip should carry a reason;
  whether repeated skips of one topic should be visible anywhere; and how a plan should report that a
  week cannot reach its horizon, which is FR-004's remaining criterion.
- Recorded as DEC-036 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the envelope and error codes this contract answers in
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology this control inherits
- [ADR-017: Record manual topic progress as a learner-owned stage](ADR-017-topic-progress-api-and-schema.md) — the any-to-any reversibility this follows, and the stage this change refuses to write
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](ADR-020-initial-study-plan-generation.md) — the plan this acts on, and the `status` column it completes
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](ADR-021-plan-item-completion.md) — the contract this extends, and the `skipped` question it left open
- [ADR-022: Adapt a study plan by rebuilding it around what happened](ADR-022-plan-adaptation.md) — the overdue rule this changes, and the adaptation a skip survives
- [ADR-023: Show today's work as a reading of the weekly plan, not a daily plan](ADR-023-daily-study-view.md) — the display partition that mirrors the changed rule
- [ADR-025: Let a learner postpone a plan item, settling it while the work waits for the next adaptation](ADR-025-learner-postponement.md) — the fourth status PLN-004 accepts, and the gap this record named
- [API conventions](../api/conventions.md) — the envelope, the error codes, and the `snake_case` rule
- [API endpoint catalog](../api/endpoints.md) — the contract this record extends
- [API versioning](../api/versioning.md) — what makes a change to it breaking
- [Database schema](../database/schema.md) — `plan_items.status`, and the first write of `skipped`
- [Domain model](../domain/domain-model.md) — rule 4, which this record applies in the other direction
- [Domain entities](../domain/entities.md) — the plan item whose status this moves
- [Terminology](../domain/terminology.md) — *skipped*, and how it differs from *postponed*
- [Functional requirements](../requirements/functional.md) — FR-004's first criterion, two of whose three verbs are now learner actions, and which this record does not claim to meet in full
- [Repository and folder structure](../development/folder-structure.md) — where the domain rule and the planner feature live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 3 item this closes
- [Architecture decision register](../architecture/decisions.md) — DEC-036
