---
title: "ADR-021: Mark a Plan Item Completed as a Reversible Statement About Work, Not About the Learner"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-09
related:
  - ../00-project-context.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-017-topic-progress-api-and-schema.md
  - ADR-020-initial-study-plan-generation.md
  - ADR-022-plan-adaptation.md
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

# ADR-021: Mark a Plan Item Completed as a Reversible Statement About Work, Not About the Learner

## Status

Accepted — 2026-08-08. Proposed 2026-08-08.

Accepted once the decision below was verified rather than merely argued. The verification the record
listed under [Implementation notes](#implementation-notes) as outstanding for the frontend is now
closed; see that section. One gap remains open there and is named as such: the PostgreSQL integration
tests have not been run on the authoring workstation, which has no PostgreSQL, so CI is their first
run.

This is the first delivery against
[FR-004](../requirements/functional.md#fr-004-plan-adaptation), and it delivers **one third** of
its first acceptance criterion: a learner can mark a planned task completed. Skipping and postponing
are deliberately not implemented, and neither is anything the other two criteria ask for.

## Implementation status — 2026-08-09

*Note added 2026-08-09. The decision above is unchanged; this records that the question this record
left open by name has been answered, and that its worst consequence is discharged.*

**Postponing work now has somewhere to go.** PLN-005 rebuilds a goal's active plans around what
happened: it leaves out topics with completed work, marks items whose day passed `postponed` on the
plan it supersedes, and re-places them on the new one. Contracted by
[ADR-022](ADR-022-plan-adaptation.md), which is **proposed rather than accepted**. It needed **no
migration**.

**Seven statements above are overtaken.** None of them was wrong when written; each described a state
of the product that has since moved.

- Under [Decision](#two-statuses-completed-and-planned-to-undo-it) — "That is the re-planning FR-004's
  second criterion asks for, which is PLN-005 and does not exist." It exists.
- The same section's reason for refusing `postponed`: "A status stored where nothing reads it and
  nothing acts on it would be a worse answer than an honest refusal." **The refusal itself is
  unchanged** — PLN-004 still accepts only `completed` and `planned`, and still answers `422`
  otherwise. What has changed is who writes `postponed`: adaptation, as it supersedes a plan, rather
  than a learner asking for it. The reasoning held; the world moved.
- Under [Decision](#only-the-item-moves) — "**Nothing is re-planned.** Generating again through
  PLN-001 remains what a learner does after a missed week, and it still supersedes rather than
  adapting." Adapting is now what a learner does after a missed week. Generating again still
  supersedes rather than adapting, and still re-plans every topic.
- Under [Consequences](#negative) — "**A completion survives a re-plan without meaning anything** …
  a learner who completed Monday and then rebuilt their plan sees that work offered again." Through
  PLN-005 they do not. Through PLN-001 they still do, which is the difference between the two
  endpoints rather than a defect in either.
- The same section's "**`skipped` remains unwritten**, so a learner who wants to abandon a topic still
  cannot say so." **Still true**, and now the only part of FR-004's first criterion outstanding.
- Under [Consequences](#neutral) — "`skipped` and `postponed` remain constrained and unwritten."
  `postponed` is written; `skipped` is not.
- Under [Implementation notes](#implementation-notes) — "**The PostgreSQL integration tests have not
  been run locally.**" They have since been, on 2026-08-09: Docker Compose works after
  [the first local run](../deployment/docker.md#first-local-run-2026-08-08), so a disposable
  `learnflow_test` database was created beside the development one and the whole suite ran green,
  **923 passed with none skipped**. The *Status* section above says this gap remains open; it no longer
  does.

**Two of the open questions this record listed are answered**: "when `skipped` and `postponed` arrive
and what postponing moves work to" — `postponed` arrives here and moves work to the plan that replaces
the one it was on — and "whether a completion should survive a re-plan", which it now does through
adaptation and deliberately does not through generation. The others stand.

**Nothing in the decision changed.** PLN-004's contract, its two accepted statuses, its reversibility,
its refusal to touch anything but the named item, and its `409` for an item on a superseded plan are
all as accepted. ADR-022 inherits that last rule rather than renegotiating it: adaptation writes
`postponed` while superseding a plan, which is a different act from a learner writing into one already
superseded.

## Context

[ADR-020](ADR-020-initial-study-plan-generation.md) generated the first study plan and stopped
exactly here. It created `plan_items.status` and `completed_at` while writing nothing but `planned`,
and recorded why: "an item without a state is not a plan item, and adding the column once learners
have plans would mean backfilling rows whose state nobody recorded". It also stated plainly that
"PLN-004 and PLN-005 belong to FR-004 and are not implemented. Nothing here moves a plan item's
status." The endpoint catalogue put the reason for the pause in its own words: both "wait on
decisions this change deliberately did not take".

Those decisions are taken here. Everything the storage needs already exists, so this change adds **no
column, no table, and no migration**. What it adds is a public contract and the rules behind it.

Six questions had to be answered, and the project owner decided each of them.

1. **Which contract.** PLN-004 has been catalogued as
   `PATCH /api/v1/plan-items/{plan_item_id}` since the documentation foundation, with the purpose
   "Mark a planned item completed, skipped, or postponed". Its request and response fields were never
   fixed.
2. **Which transitions, and whether completion is reversible.** `plan_items.status` accepts four
   values. FR-004 asks for three of them.
3. **What else moves.** The same topic appears as a roadmap item and as a weekly item, and
   [FR-005](../requirements/functional.md#fr-005-topic-progress-and-learning-evidence) has a
   learning stage sitting one table away.
4. **What happens to an item on a superseded plan.** ADR-020 keeps superseded plans and promises they
   read "exactly as written".
5. **The write topology.** ADR-015 and every screen since have kept the browser away from the API.
6. **Whether this needs an ADR at all**, given that the endpoint was already catalogued.

## Decision

### PLN-004 as catalogued, with `status` as its only field

`PATCH /api/v1/plan-items/{plan_item_id}` takes `{"status": "…"}` and returns `200` with the whole
item under `data`. No endpoint is invented and no catalogued path is changed.

**The item is addressed by its own identifier**, not through its plan. A learner acting on one line
should not have to name the plan it came from, and the item's plan is what the server reads to decide
whether the item is theirs.

**`completed_at` is not accepted from a client.** It is the server's record of *when the learner said
so*, read from the same `Clock` port ADR-020 introduced. Accepting one would let a caller backdate
work, and an unknown field is a `422` rather than being ignored — the rule PLN-001 already applies.

**The whole item comes back**, not the status alone, so a client can re-render the line it changed
without reading the plan again.

### Two statuses: `completed`, and `planned` to undo it

`planned` and `completed` are accepted. `skipped` and `postponed` are refused with a `422` naming
what *is* accepted and saying they are not built yet.

**They are refused rather than stored** because postponing work raises a question this change cannot
answer: postponed *to when?* That is the re-planning FR-004's second criterion asks for, which is
PLN-005 and does not exist. A status stored where nothing reads it and nothing acts on it would be a
worse answer than an honest refusal.

**Completing is reversible.** A learner who marked the wrong line sends `planned` and the timestamp
is cleared. Nothing in LearnFlow treats finishing work as a verdict, and this is the same position
[ADR-017](ADR-017-topic-progress-api-and-schema.md) took on a learning stage: a learner may move to
any stage from any stage, including backwards. A one-way button would be the product forming an
opinion about a mis-tap.

**Sending the status an item already holds is accepted and writes nothing**, which is PRG-004's rule
for the same reason: a repeated form submission must not fail on its second attempt.

`status` and `completed_at` move together. An item is completed at an instant or it is not completed
at all, so a `planned` item never carries a timestamp and a `completed` one always does.

### Only the item moves

The write touches `plan_items.status` and `plan_items.completed_at` on **one row**. It does not touch
the plan, any other item, or `learner_topic_progress`.

**A completed weekly item leaves the matching roadmap item `planned`**, and that is the decision
rather than an oversight. The two are related only by naming the same topic; no column links them, a
plan may legitimately name a topic twice, and inferring a link the schema does not store would make
the plan mean something the data does not say. The learner sees two items and may mark either.

**No learning stage is written.** This is rule 4 of the
[domain model](../domain/domain-model.md) — "a plan item records whether planned work happened; it
does not automatically mean the topic is mastered or completed" — and it is the same refusal ADR-020
made when it declined to reorder a plan by stage. Completing a plan item is a statement about the work;
a learning stage is the learner's own statement about their understanding, and PRG-004 is where they
make it.

**Nothing is re-planned.** Generating again through PLN-001 remains what a learner does after a
missed week, and it still supersedes rather than adapting. The trade-off-aware re-plan FR-004's third
criterion asks for is PLN-005.

**Nothing is counted.** No progress bar, no "3 of 7 completed", no percentage — on the API or the screen.
ADR-020 established that nothing totals a day, a week, or a plan; a completion count is the same
second opinion in a new form, and `priority` remains an order rather than a score.

### An item on a superseded plan cannot be moved

Only an item whose plan is `active` may be completed. One on a superseded plan is refused with `409`
`conflict`, and the message points the learner at their current plan.

A superseded plan is kept **because** it reads exactly as it was written (ADR-020). Writing into one
would change the record whose entire worth is that it does not change. This is a state conflict
rather than a rejected field, which is what `conflict` means in the
[error catalogue](../api/conventions.md#error-codes).

### The write goes through a Next.js server action, and the backend gains no CORS

The control on `/plan` posts to a `"use server"` module which calls the API with the same server-side
`API_BASE_URL` every view uses, then revalidates `/plan`. The browser still issues no request to the
backend, so `API_CORS_ALLOWED_ORIGINS` stays planned rather than implemented.

This inherits [ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md) through
ADR-020 rather than renegotiating them. The form works without JavaScript.

**The control appears on both panels**, the roadmap and the week. A plan item is a plan item whichever
panel shows it, and a learner working ahead of their week should not have to wait for a topic to
appear there. A completed item **stays where it is** rather than moving or disappearing: the plan is
the record of what was planned, and hiding finished work would leave a roadmap short of a topic and a
day looking undone.

An item in a status the API does not accept — `skipped` or `postponed`, which nothing writes — is
shown as the API sent it with no control, rather than being presented as something a learner can move.

### No new domain rule

`backend/app/domain/study_planning.py` is untouched. Deciding which status a learner may ask for is a
contract check rather than a planning calculation, and it needs the stored plan's own state to answer
— so it belongs in `ManageStudyPlans` beside the ownership rules, which is where every other
"is this the learner's, and may they do this" decision already lives.

## Consequences

### Positive

- **A learner can act on their plan for the first time.** Every plan screen before this was
  read-only, and a plan a learner cannot mark up is a document rather than a tool.
- **No migration, no column, no table.** ADR-020's argument for creating `status` and `completed_at`
  early is discharged exactly as it predicted: the state was there when the code that writes it
  arrived, so no row had to be backfilled by guessing.
- **The reversal costs nothing to offer** and removes the one thing that would have made the control
  feel risky.
- **No new error code was needed.** `validation_error`, `not_found`, and `conflict` all existed.
- **The distinction between doing work and understanding a topic is now visible in the product**, not
  just in the schema: two separate controls on two separate screens, neither writing the other.

### Negative

- **A fourth endpoint is public contract.** Changing a field or a status code on it is breaking under
  [versioning](../api/versioning.md#breaking-changes).
- **FR-004's first criterion is only a third met.** A learner who wants to skip a topic or move it to
  next week has no way to say so, and the `422` tells them it is not built rather than offering an
  alternative.
- **The same topic can read `completed` on the week and `planned` on the roadmap.** That is the
  decided behaviour, and it will look inconsistent to a learner who does not know the two are separate
  items. Nothing on the screen explains the relationship, because nothing in the data states it.
- **A completion survives a re-plan without meaning anything.** Generating again supersedes the plan
  the completed item belongs to, and the new plan's items all start `planned` — so a learner who
  completed Monday and then rebuilt their plan sees that work offered again. Nothing carries
  completion forward, because carrying it forward is re-planning.
- **`completed_at` is a UTC instant while every other date in a plan is a calendar date** in the
  learner's own zone. Nothing displays the instant today, so no screen has yet had to reconcile them.

### Neutral

- Nothing here totals, ranks, or scores anything, and no percentage is reported.
- `skipped` and `postponed` remain constrained and unwritten, as `monthly`, `daily`, `practice`,
  `revise`, and `review_mistakes` do. Each arrives with the code that writes it.
- The domain layer still holds exactly one module.
- No command-line tool completes a plan item.

## Alternatives considered

### Accept all four statuses now

`completed`, `skipped`, and `postponed` in one change, which is FR-004's first acceptance criterion
outright.

**Not selected:** postponing has no destination until PLN-005 exists, so a postponed item would sit
in a status nothing reads and nothing acts on — the learner would have told the product something it
cannot use. Skipping is closer to viable, but it belongs with the same re-planning question: a plan
that knows work was skipped and does nothing about it is not obviously better than one that does not
know.

### Make completion one-way

`planned → completed` only, on the reading that a plan is a record of what happened and a record
should not be edited.

**Not selected:** the record being edited is the learner's own statement, made seconds earlier, about
their own work. Nothing else in LearnFlow is one-way — a learning stage moves backwards deliberately
(ADR-017) — and an irreversible button on a list of sixty items makes a mis-tap permanent.

### Complete the matching roadmap item too

Completing a weekly item also completes the roadmap item naming the same topic.

**Not selected:** it invents a linkage the schema does not store. The two items are related only by
topic, a plan may name a topic more than once, and the "matching" item would have to be found by
searching the goal's other active plan. A learner completing one plan item has said that item's
work happened, not that a topic is finished with.

### Write a learning stage when an item is completed

Advance `learner_topic_progress` when a plan item for a topic is marked completed.

**Not selected:** domain rule 4 and FR-005 both forbid it — "the product does not claim permanent
mastery from one quiz or one manual update", and completing a planned session is exactly one such
update. It is also the same refusal ADR-020 made in the other direction when it declined to let a
stage reorder a plan.

### Allow completion on a superseded plan

Any item the learner owns can be moved, whatever its plan's status.

**Not selected:** it would break the promise that a superseded plan reads exactly as it was written,
which is the entire reason ADR-020 keeps them. The completion would also land on a plan no screen
shows, so the learner would see no result from an action that succeeded.

### A `POST /plan-items/{id}/complete` action endpoint

Narrower than a `PATCH`, and unambiguous.

**Not selected:** it is not the catalogued contract, and undoing would need either a second endpoint
or a `PATCH` beside it — at which point the `PATCH` is doing the work anyway. Skipping and postponing
would each need their own path later.

## Implementation notes

- Endpoint fields and per-endpoint error codes are in
  [api/endpoints.md](../api/endpoints.md#pln-004-patch-apiv1plan-itemsplan_item_id), which stays
  authoritative.
- **No migration.** `plan_items.status`, its `CHECK`, and `completed_at` were all created by
  `20260806_03`; this change is the first caller of columns that were already there.
- `PLAN_ITEM_STATUS_CHANGES` lives in `application/dto/study_plan.py` beside `PLAN_ITEM_STATUSES`.
  The two are deliberately separate: one is what a learner may *ask for*, the other is what the column
  may *hold*, and the `CHECK` mirrors only the second.
- `ManageStudyPlans.record_item_status` serves the endpoint, so the rule deciding whether a plan or an
  item belongs to the effective learner stays in one place. Its existing provider in
  `composition/providers.py` already owns the transaction.
- `StudyPlanRepository` gained `find_plan_item` and `update_plan_item`. Ownership is not filtered in
  either, matching `find_study_plan`: whether a record is the learner's is a rule.
- The route is `presentation/api/routes/plan_items.py` at its own prefix, tagged `study-plans` so the
  generated documentation keeps the planning endpoints together.
- The frontend is `features/planner/PlanItemStatusControl.tsx`, with `savePlanItemStatus` added to the
  existing `actions.ts` and its state shape in `submission.ts` — because a `"use server"` module may
  export only async functions, which `frontend/tests/server-actions.test.ts` enforces.
- **The PostgreSQL integration tests have not been run locally.** Six were added to
  `tests/integration/test_study_plan_api.py` and CI runs them; they skip on a workstation with no
  `TEST_DATABASE_URL`. The unit and API suites, which do run, cover the rules and the contract but not
  the SQL.
- **This change has been exercised against the production standalone frontend with a contract-shaped
  stub API, with JavaScript disabled.** Twenty-five checks passed. The run enforced "no JavaScript" by
  never running any: it issued raw HTTP requests and submitted the form as a scriptless browser
  does — a native multipart POST to the page's own URL carrying the `$ACTION_*` fields Next.js
  renders — so a control that only worked once hydrated could not have passed.

  Verified: `/plan` renders a completion control beside all four items on both panels, each posting
  the status it will set; the form carries `method="POST"`, `enctype="multipart/form-data"`, and an
  empty `action`, which is the progressive enhancement; a no-JavaScript submission reached PLN-004
  **exactly once**, at `/api/v1/plan-items/{id}`, with the body `{"status":"completed"}` and nothing
  else; the item read back as completed, kept its place and its reason, and offered *Return to
  planned*; **only that item moved** — one completed label rendered and the other three items,
  including the roadmap item naming the same topic, still offered completion; the undo submission
  cleared it and restored the original control; an item on a superseded plan was refused, the stub
  answering `409`, with the learner shown the action's own wording rather than the backend's; no
  completion count or percentage appeared anywhere; and no API address appeared in the HTML of
  `/plan`, `/`, `/setup`, or `/curriculum`, nor in any of the twelve client scripts they load.

  **Two assertions in the first run failed and both were defects in the harness, not the product.**
  The form check looked for a lowercase `enctype` and a non-empty `action`, where React serialises
  `encType` and a server action renders `action=""`; and the "only one item moved" check stripped
  `<script>` blocks to avoid counting the React Server Component payload, which streams in chunks a
  lazy regex mis-aligns on. Counting rendered element text instead settled it: one label in the
  document, one copy in the payload.
- Open and deliberately not settled here: when `skipped` and `postponed` arrive and what postponing
  moves work to; whether a completion should survive a re-plan; whether the roadmap and the week
  should be linked at all; and whether a completed item should ever be displayed with its
  `completed_at`.
- Recorded as DEC-033 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](ADR-011-sqlalchemy-persistence-implementation.md) — the validated-text rule the `status` `CHECK` follows
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the envelope and the error codes this contract answers in
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology this control inherits
- [ADR-017: Record manual topic progress as a learner-owned stage](ADR-017-topic-progress-api-and-schema.md) — the reversible-by-design precedent, and the stage this change refuses to write
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](ADR-020-initial-study-plan-generation.md) — the plan this acts on, the columns it left ready, and the supersede lifecycle it must not break
- [API conventions](../api/conventions.md) — the envelope, the error codes, and the `snake_case` rule
- [API endpoint catalog](../api/endpoints.md) — the contract this record decides
- [API versioning](../api/versioning.md) — what makes a change to it breaking
- [Database schema](../database/schema.md) — `plan_items`, and the two columns this change is the first to write
- [Domain model](../domain/domain-model.md) — rule 4, which this record applies
- [Domain entities](../domain/entities.md) — the plan item whose status this moves
- [Terminology](../domain/terminology.md) — *plan item*, and the *complete* ambiguity this wording avoids
- [Functional requirements](../requirements/functional.md) — FR-004's first criterion, and FR-005's refusal to claim mastery
- [Repository and folder structure](../development/folder-structure.md) — where the route and the planner feature live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 3 item this partly closes
- [ADR-022: Adapt a study plan by rebuilding it around what happened](ADR-022-plan-adaptation.md) — the re-planning that answers what postponing moves work to, and the first write of `postponed`
- [Architecture decision register](../architecture/decisions.md) — DEC-033
