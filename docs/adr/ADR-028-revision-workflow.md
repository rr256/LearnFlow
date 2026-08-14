---
title: "ADR-028: Schedule Revisions from Finished Work, on the Learner's Ask"
status: accepted
owner: architecture-and-data
last_updated: 2026-08-13
related:
  - ../00-project-context.md
  - ADR-011-sqlalchemy-persistence-implementation.md
  - ADR-014-api-response-contract.md
  - ADR-015-frontend-foundation-and-server-rendered-api-access.md
  - ADR-017-topic-progress-api-and-schema.md
  - ADR-020-initial-study-plan-generation.md
  - ADR-021-plan-item-completion.md
  - ADR-022-plan-adaptation.md
  - ADR-023-daily-study-view.md
  - ADR-024-plan-item-skipping.md
  - ADR-025-learner-postponement.md
  - ADR-026-monthly-study-view.md
  - ADR-027-plan-feasibility.md
  - ../api/conventions.md
  - ../api/endpoints.md
  - ../api/versioning.md
  - ../database/schema.md
  - ../database/migrations.md
  - ../domain/domain-model.md
  - ../domain/entities.md
  - ../domain/terminology.md
  - ../requirements/functional.md
  - ../development/coding-standards.md
  - ../development/folder-structure.md
  - ../roadmap/milestones.md
  - ../architecture/decisions.md
---

# ADR-028: Schedule Revisions from Finished Work, on the Learner's Ask

## Status

Accepted — 2026-08-13. Proposed 2026-08-13.

Accepted once the decision below was verified rather than merely argued. **Nothing in the decision
changed on acceptance**, and nothing is recorded here as unverified. The whole canonical check set is
green — the backend suite with warnings as errors (**901 passed**), Ruff lint and format, the frontend
lint, type check, **535 tests**, and production build, the `scripts/` checks, and the documentation
validator. The **PostgreSQL integration tests were run locally** against the disposable
`learnflow_test` database (**257 passed**), including twenty over migration `20260813_01` — its
upgrade, its **downgrade**, every documented status and trigger, the constraints it refuses, its
foreign keys, and its index. The development `learnflow` database was not touched: `alembic_version`
stayed at `20260806_03`, `revision_records` does not exist there, and its row counts and `plan_items`
fingerprint were identical before and after.

The **scriptless standalone-frontend run was performed** against a contract-shaped stub API with the
server on `TZ=UTC`: **68 checks passed**, plus three for the unreachable-API panel. See
[Implementation notes](#implementation-notes) for what it demonstrated.

This delivers the **built** part of
[FR-006](../requirements/functional.md#fr-006-revision-guidance) — revision scheduling, status
updates, and a view of what is due — and creates `revision_records`, the table the *Progress and
revision* schema area has been missing since the documentation foundation. It is the last of
[Milestone 3](../roadmap/milestones.md#milestone-3-planning-and-revision)'s requirements to be
started. **FR-006 is not met in full**, and this record does not claim it is.

**Two of FR-006's four acceptance criteria are met in full:**

- **"The learner can see topics due for revision."** REV-001 lists them, earliest due date first,
  with `is_due` decided by a domain rule.
- **"Completing or skipping a revision is recorded."** REV-003 records `completed`, `skipped`,
  `postponed`, or back to `due`, every move reversible.

**One criterion is partly met.** The fourth — "revision recommendations can consider completion,
learning stage, quiz/test evidence, and prior revision history" — considers **three of its four
inputs**: completion creates a revision, the recorded learning stage times it, and a completed review
schedules the next. **Quiz and test evidence is not considered**, because none is stored:
`quiz_attempts`, `external_test_results`, and `mistake_evidence` do not exist. `trigger_type` is
where such a source would be named when it does.

**One criterion is deferred.** The second — "a revision recommendation links to a topic and, where
available, relevant resource or practice suggestions" — links its topic, and **the resource and
practice half is deferred**: it depends on
[FR-007](../requirements/functional.md#fr-007-learning-resource-organization)'s resources and
[FR-009](../requirements/functional.md#fr-009-topic-checkpoint-practice)'s checkpoint quizzes, and
neither exists. The screen suggests nothing rather than implying suggestions are available, and this
criterion is completed by the change that builds those features — not by this one.

It is the **first change in this series to need a migration**: `20260813_01`, one `CREATE TABLE` and
one index. Nothing existing is altered.

## Context

`revision_records` has been an approved table with no code since Milestone 0, and
[schema.md](../database/schema.md#implementation-review-required) has carried *the actual
revision-scheduling rules* as a pending review input for the learner-planning and progress areas since — ADR-020 recorded
it as outstanding for `study_plans` and `plan_items`, and ADR-021 through ADR-025 each restated it.
This is the change that supplies them.

Seven questions had to be answered, and the project owner decided each of them.
[ADR-014](ADR-014-api-response-contract.md) had already fixed the envelope and the error catalogue,
so none of that was open.

1. **What creates a revision, and when.**
2. **What decides its due date.**
3. **Whether completion alone drives it, or learning stages too.**
4. **Where revisions appear** — inside the weekly and daily plan, or somewhere of their own.
5. **How a learner records what became of one.**
6. **Whether revisions affect plan adaptation.**
7. **The storage, the API contract, the route, and whether this needs an ADR.**

### One finding that shaped the answers

**Everything a revision needs is already stored, except the revision itself.** A completed plan item
carries its topic and its `completed_at`; a learning stage carries the learner's own view of the
topic. So the only new storage is the record of the review and what became of it — which FR-006's
third criterion requires be stored, because a completion is a statement that must persist.

That is also why this could not be a *reading*, as ADR-023, ADR-026, and ADR-027 each were. Those
three answer questions from records that exist. A revision **is** a record: nothing else in the
system can say that a learner reviewed a topic on a day.

## Decision

### The learner asks; nothing schedules on its own

Revisions are created by `POST /api/v1/revisions/schedule` (REV-004), and at no other time.
**Completing a plan item creates no revision**, and neither does completing a revision.

This is ADR-021's "only the named item moves" applied to a second record type, and ADR-022's "the
learner asks; nothing adapts on its own" applied to a second capability. It is also what the task
constraint requires: no background job, no scheduler, no side effect on PLN-004. A learner ticking
items off a list must not have a second list grow underneath them.

**Creating revisions as a side effect of PLN-004 was rejected**, under *Alternatives*. So was
deriving them on read: a derived revision has nowhere to record that the learner completed it.

**Asking twice creates nothing the second time.** A topic with a revision already waiting is passed
over, and the response says how many were left alone — so a repeated form submission is safe, which
is the property ADR-020 required of a repeated generation.

### A topic returns an interval after the work, and the interval comes from the learning stage

`interval_for_stage` and `due_on` are **pure functions in
`backend/app/domain/revision_scheduling.py`**, the domain layer's second module. The intervals are:

| Recorded stage | Days |
| --- | --- |
| none recorded, or `not_explored` | 7 |
| `building_foundation` | 7 |
| `developing_confidence` | 10 |
| `practice_ready` | 14 |
| `strong_understanding` | 21 |

**These are LearnFlow's intervals, not the learner's**, and every revision says so in its own
words — the promise ADR-020 keeps for its 60-minute session and ADR-019 requires of any unset
preference. A learner has recorded a stage, not a schedule.

**A longer interval is not a better mark.** A stage the learner recorded says what they think of
their own understanding, and a topic they are confident with is worth seeing again later than one
they are still building. That is the *supportive next action* a stage exists to guide
([FR-005](../requirements/functional.md#fr-005-topic-progress-and-learning-evidence)), and FR-006's
fourth criterion names the learning stage as a revision input explicitly.

**This does not breach ADR-020's refusal to let a stage reorder a plan.** That refusal is about
*planning* — which topic comes first, and how long a session runs — and it stands untouched. FR-006
sanctions the stage for *revision timing*, which is a different question about a different record.
Nothing here ranks two topics against each other, scores the learner, or compares anything.

**A stage this build does not recognise falls back to the seven-day interval** rather than failing,
so a backend that later grows a sixth stage schedules something sensible instead of leaving the
learner with no revisions.

### Completed work creates a revision; the stage only times it

A topic gets a revision when the learner **completed planned work on it**. A recorded stage alone
creates nothing: a learner who marked a topic `practice_ready` without finishing any planned work
has not finished anything to review, and creating one would be the product inventing work they never
did.

The completion is taken from the **earliest** completed plan item for that topic across every one of
the learner's plans, **superseded ones included** — superseding a plan does not un-complete the work
done under it, which is ADR-022's rule and the one adaptation applies. The earliest rather than the
latest, so a learner who completed the same topic on two plans is offered review from when they first
finished it rather than having the clock reset by a repeat.

### Prior revision history: a completed review schedules the next

A topic whose latest revision the learner **completed** comes back again, dated from *that*
completion by the same interval table, with `trigger_type = 'completed_revision'`. That is what makes
review spaced rather than single, and it is FR-006's fourth criterion naming *prior revision history*
as an input.

**A revision the learner skipped or postponed is left alone.** They have said what became of that
review, and scheduling does not overrule them — the same respect ADR-024 and ADR-025 established for
a settled plan item. Nothing is lost by it: every status is reversible through REV-003, so a learner
who changes their mind puts the review back themselves. This is deliberately *not* the plan-item
rule, where a skipped topic **is** planned again; the difference is that a plan is rebuilt wholesale
and a revision is not, so leaving one alone is the only way to honour the answer.

### Revisions are their own records, on their own screen

A revision is **not** a plan item. `plan_items.action_type = 'revise'` stays unwritten, and no
revision is written into a `weekly`, `daily`, `roadmap`, or `monthly` plan.

**This is the decision most likely to be argued with**, because `revise` exists and is inviting. The
reason it is refused is lifecycle: **adaptation supersedes every active plan of a goal**, and a
revision the learner has acted on must survive that. A review recorded as a plan item would be
destroyed — or at best frozen onto a superseded plan the learner cannot edit — by an unrelated action
on their study plan. The two records have different lifetimes, so they are different records.

They live at **`/revisions`**, a route of its own, linked from `/`, `/plan`, `/plan/today`, and
`/plan/month`. **The four plan views are untouched**: the roadmap, the week, the day, and the month
render exactly as they did, and the setup → study → complete/skip/postpone → update flow is
unchanged.

### REV-003 mirrors PLN-004 exactly

`PATCH /api/v1/revisions/{revision_id}` accepts `due`, `completed`, `skipped`, and `postponed`, from
whichever the revision currently holds. Every move is allowed and every one is reversible; nothing is
one-way.

That is deliberately the same shape a plan item has, because a learner who has learned to mark a plan
item should not have to learn a second vocabulary for a review. `completed_at` is read from the
server's clock and cleared by any move off `completed`; there is **no `skipped_at`**, **no date**, and
**no reason field** — asking why a learner skipped a review would invite the product to form a view
about the answer, which FR-005 refuses and terminology names as wording to avoid.

The labels differ from a plan item's because the subject does: a review is *reviewed*, not
*completed*.

**`scheduled` and `scheduled_for` are created and left unwritten.** Naming a day for a review is a
second capability — it raises what happens when that day passes and whether the schedule or the
learner owns the date — and inventing it alongside the first would be two features in one change. The
`CHECK` carries the value so it arrives as a use-case change rather than a migration, which is the
argument ADR-020 made for `plan_items.status` and which paid off three times. REV-003 refuses it,
because a caller asking for it would be asking for a date nothing collects.

### Revisions do not affect plan adaptation

PLN-005 is untouched. Adaptation reads plans and plan items; it does not read, write, create, or
supersede a revision, and a revision does not change which topics a plan covers.

The two are deliberately independent. A plan says what to study next; a revision says what to revisit.
Coupling them would mean a learner rebuilding their plan silently rescheduling their reviews, which
is exactly the surprise ADR-022 exists to prevent.

### Nothing writes a learning stage

Rule 4 of the [domain model](../domain/domain-model.md#domain-rules-and-invariants) reads here as it
does for a plan item: a revision records whether **a review happened**, never that a topic is
understood. Completing a review writes no stage, and nothing derives one.

The stage is **read** — it decides how long a topic waits — and never written. That keeps ADR-017's
`stage_source` meaningful: every stage stored is still `learner`.

### `recommendation_reason`, a column the approved table does not list

`revision_records` is created with the ten columns
[schema.md](../database/schema.md#revision_records) documents, **plus `recommendation_reason`**.

**This is a departure, and it is deliberate.** A revision's due date is computed from the learning
stage recorded *at the moment it was created*. A learner who later moves a topic from
`building_foundation` to `strong_understanding` has changed nothing about a revision already
scheduled — but a reason recomputed from the current stage would then say "21 days" beside a date
seven days out. **The stored date and its explanation would contradict each other.**

Freezing the sentence when the revision is created keeps the record self-explaining, which is exactly
the guarantee `plan_items.recommendation_reason` and `study_plans.generation_reason` carry and the
reason ADR-020 gave for them: a record kept as history must read in the terms that produced it. It is
also what lets a learner answer *why is this due today* without the product reconstructing an answer
it can no longer verify.

`status` and `trigger_type` are `varchar(32)` guarded by a `CHECK` rather than the bare `text` the
document's table describes — the departure ADR-018 made for `day_of_week`, ADR-019 for
`topic_sequencing`, and ADR-020 for the plan columns, for the same reason.

**`trigger_type` permits only the two values something writes.** The document describes it as holding
"why revision was created, e.g. completion, low evidence, spaced schedule"; low evidence needs quiz
and external-test records, which do not exist. A third value arrives with the evidence that justifies
it.

### Four endpoints, three of them catalogued

REV-001, REV-002, and REV-003 are implemented as
[endpoints.md](../api/endpoints.md#revision-endpoints) catalogues them. **REV-004 is new**, and the
catalogue is amended rather than filled in — the departure ADR-022 made for PLN-005, for a comparable
reason: something has to create the record, nothing may create it automatically, and none of the
three catalogued endpoints does.

The screen reads through the same server-side API client every view uses, and both write paths post
to a `"use server"` module. The browser issues no request to the backend, so
`API_CORS_ALLOWED_ORIGINS` stays planned. This inherits
[ADR-015](ADR-015-frontend-foundation-and-server-rendered-api-access.md) through ADR-027 rather than
renegotiating them, and every form works without JavaScript.

## Consequences

### Positive

- **FR-006's revision scheduling, status updates, and due-review view are delivered**, which is the
  last of Milestone 3's requirements to be started. **Two of its four criteria are met in full**, a
  third is met on three of its four inputs, and the resource-and-practice half of the second is
  **deferred** to FR-007 and FR-009. See [Status](#status) for the breakdown.
- **The *Progress and revision* schema area gains its second table**, and the *revision-scheduling
  rules* review input that has been pending against every schema area since Milestone 0 is
  discharged.
- **The domain layer gains a second module**, and both its rules are pure: how long a topic waits and
  which reviews are due are testable exhaustively without a clock or a database.
- **Nothing existing changed.** No plan, plan item, availability, preference, goal, or stage behaves
  differently, and the migration alters no existing table.
- **A revision survives adaptation**, which is the property that made a separate table worth its
  cost.
- **A learner meets one vocabulary, not two.** Marking a review reuses PLN-004's shape, its
  reversibility, and its refusal to record a reason.
- No new error code was needed: `validation_error`, `not_found`, and `conflict` all existed.

### Negative

- **A fourth endpoint group is public contract**, and one of the four departs from the catalogue.
  Changing any of them is breaking under [versioning](../api/versioning.md#breaking-changes).
- **The intervals are invented numbers.** Seven to twenty-one days is a defensible spread and it is
  named as LearnFlow's own everywhere it appears, but no evidence in this product supports those
  figures over any other, and nothing lets a learner change them.
- **A learner must ask before anything is scheduled.** Someone who never presses the control sees no
  reviews at all, however much work they finish. That is the deliberate cost of refusing automatic
  behaviour, and the screen says what the button does — but the product cannot remind them.
- **A skipped or postponed review ends that topic's schedule** until the learner reopens it. That
  respects their answer, but it means a postponement is not the "come back later" a learner might
  expect. The confirmation says so explicitly.
- **`_today_for` now exists twice**, in `manage_study_plans` and `manage_revisions`. Extracting it is
  a refactor across a module this change otherwise does not touch, and it is recorded here rather
  than done quietly.
- **A fifth learner-facing route** is another surface that must keep its loading, empty, error, and
  success states in step with the contract behind it.
- **`revision_records` is the first table to carry a column its approved shape does not list.** The
  reasoning is above; the cost is that schema.md and the migration must be read together.

### Neutral

- Nothing here totals, counts, ranks, or scores. No "3 due", no streak, no percentage, no revision
  count — the line [terminology](../domain/terminology.md#plan-coverage-counts-are-not-learner-scores)
  draws. `already_scheduled_topic_count` describes what a run left alone, which is a fact about the
  run.
- No AI provider is involved, and no configuration variable is read. The same finished work, stages,
  and date produce the same revisions.
- `scheduled`, `scheduled_for`, and `plan_items.action_type = 'revise'` are all constrained and
  unwritten, as `monthly`, `daily`, `practice`, and `review_mistakes` remain.
- `study_activities` is still absent, so the *Progress and revision* area is still incomplete.
  PRG-001 still needs it, and ACT-001 and ACT-002 stay uncontracted.
- No command-line tool schedules a revision.

## Alternatives considered

### Create a revision when a plan item is completed

PLN-004 would write a revision as a side effect, so a learner never has to ask.

**Not selected:** it breaks ADR-021's accepted decision that completing an item moves "no plan, no
other item … and no learning stage", by having it create a record in a different table entirely. It
would also make a mis-tap expensive — completing an item by accident would schedule a review — and it
gives the learner no moment at which they chose. The task constraint refuses automatic behaviour, and
this is the clearest case of it.

### Derive revisions on read, storing nothing

`GET /api/v1/revisions` would compute what is due from completed plan items and stages, as ADR-023,
ADR-026, and ADR-027 each compute their answers.

**Not selected:** FR-006's third criterion requires that completing or skipping a revision be
*recorded*, and a derived revision has nowhere to record it. It would also make prior revision history
impossible — the fourth criterion — because there would be no history.

### Write revisions as plan items with `action_type = 'revise'`

The value exists and is unwritten, and it would put reviews in front of the learner on the daily view
with no new screen.

**Not selected**, and this is the largest of the alternatives. Adaptation supersedes every active plan
of a goal, so a review recorded as a plan item would be destroyed or frozen by an action about
something else. It would also make `item_count` mean two things, put revision scheduling inside the
planner's supersede lifecycle, and force every future planning change to reason about reviews.

### Refuse `postponed` on a revision

Offer `completed` and `skipped` only, on the ground that a review has no date to move to.

**Not selected:** the learner's meaning is clear enough — *not yet* — and the four statuses are four
answers to one question, which is the position ADR-025 reached for a plan item. What it moves to is
the next scheduling run, which the confirmation says.

### Let the learner choose the intervals

A planning preference for revision spacing, beside session length and topic order.

**Not selected** *for this change*: it is a second capability with its own contract, its own
migration, and its own questions about what happens to revisions already scheduled under the old
spacing. The intervals being LearnFlow's own is stated everywhere they appear, which is the honest
interim position. It is a natural follow-up.

### Reuse the plan item's `SETTLED_STATUSES` semantics exactly

Treat a skipped or postponed revision as adaptation treats a skipped plan item: leave the record
alone, but schedule the topic again on the next run.

**Not selected:** a plan is rebuilt wholesale, so a skipped plan item's topic reappears in a *new*
plan without contradicting the old record. Revisions are not rebuilt, so scheduling the same topic
again would put a second live review beside one the learner had just answered. Leaving it alone, and
making the answer reversible, respects the statement instead.

## Implementation notes

- Endpoint fields and per-endpoint error codes are in
  [api/endpoints.md](../api/endpoints.md#revision-endpoints), which stays authoritative.
- Migration `20260813_01_create_revision_records_table` creates one table and one index and alters
  nothing. Its downgrade drops both, index first, and names no constraint — dropping a table takes
  its checks with it, which also keeps the downgrade clear of the `ck` naming convention that bit
  revision `20260806_02`. [migrations.md](../database/migrations.md#commands) records that trap.
- `REVISION_STATUSES`, `REVISION_STATUS_CHANGES`, `REVISION_TRIGGERS`, and
  `SETTLED_REVISION_STATUSES` live in `application/dto/revision.py` and are mirrored by the model's
  `CHECK`s, the way the plan vocabularies are.
- `ManageRevisions` serves all four endpoints, so the rule deciding whether a revision belongs to the
  effective learner stays in one place. Its provider in `composition/providers.py` owns the
  transaction, so a run creating several revisions cannot half-succeed.
- `RevisionRepository` gained `list_completed_topic_work`, which groups the earliest completion per
  topic **in SQL**, so a learner with many superseded plans does not pull every completed item across
  the boundary to discard most of them. `list_recorded_stages` is scoped by topic rather than by
  curriculum version, unlike the planner's, because a revision names a topic and belongs to no goal.
- The frontend is `app/revisions/page.tsx` with `features/revision/` —
  `RevisionList.tsx`, `RevisionStatusControl.tsx`, `ScheduleRevisionsForm.tsx`, `actions.ts`, and the
  form state in `submission.ts` because a `"use server"` module may export only async functions,
  which `frontend/tests/server-actions.test.ts` enforces.
  `scheduleRevisionsAction` takes no parameters at all: REV-004 has no request body, so there is
  nothing on the form to read.
- Covered at five levels: pure domain tests for the intervals and the due boundaries; use-case tests
  against fakes with a fixed clock; API contract tests over the real application factory; PostgreSQL
  integration tests over the migration, its constraints, and its index; and frontend tests over the
  list, the control, the form parsing, and the API client.
- **The verification this record carries is recorded in the delivery report**, including the
  PostgreSQL run against the disposable `learnflow_test` database and the scriptless
  standalone-frontend run.
- Open and deliberately not settled here: whether the intervals should become a planning preference;
  whether `scheduled` and `scheduled_for` are ever written; whether a revision should ever appear in
  the daily study view; whether quiz and external-test evidence should later create revisions
  (`trigger_type` is where that would go); and whether `_today_for` should be extracted to a shared
  module.
- Recorded as DEC-040 in [the decision register](../architecture/decisions.md).

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-011: Implement PostgreSQL persistence synchronously and migrate per milestone](ADR-011-sqlalchemy-persistence-implementation.md) — the migrate-with-the-code rule this change follows, and the validated-text rule it applies again
- [ADR-014: Fix the public HTTP API response contract](ADR-014-api-response-contract.md) — the envelope these four contracts answer in
- [ADR-015: Build the frontend on Next.js and reach the API from the server](ADR-015-frontend-foundation-and-server-rendered-api-access.md) — the call topology this screen inherits
- [ADR-017: Record manual topic progress as a learner-owned stage](ADR-017-topic-progress-api-and-schema.md) — the stage this reads to time a revision and refuses to write
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](ADR-020-initial-study-plan-generation.md) — the frozen-reason guarantee this reuses, and the `revise` action type it leaves unwritten
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](ADR-021-plan-item-completion.md) — the completions that create a revision, and the "only the named item moves" rule that keeps creation manual
- [ADR-022: Adapt a study plan by rebuilding it around what happened](ADR-022-plan-adaptation.md) — the supersede lifecycle a revision must survive, and why it is not a plan item
- [ADR-024: Let a learner skip a plan item, settling the item without retiring the topic](ADR-024-plan-item-skipping.md) — the settled semantics this follows, and the one place it deliberately differs
- [ADR-025: Let a learner postpone a plan item, settling it while the work waits for the next adaptation](ADR-025-learner-postponement.md) — the any-to-any reversibility REV-003 mirrors
- [ADR-027: Report whether the saved week reaches the horizon, as a read-only planning rule](ADR-027-plan-feasibility.md) — the most recent domain rule, and the reading this change is deliberately not
- [API conventions](../api/conventions.md) — the envelope, the error codes, and the `snake_case` rule
- [API endpoint catalog](../api/endpoints.md) — the three contracts this implements and the fourth it adds
- [API versioning](../api/versioning.md) — what makes a change to them breaking
- [Database schema](../database/schema.md) — the approved table, and the two departures this record makes from it
- [Database migrations](../database/migrations.md) — the migration this record introduces
- [Domain model](../domain/domain-model.md) — the revision record, and rule 4 this change applies again
- [Domain entities](../domain/entities.md) — the entity this persists
- [Terminology](../domain/terminology.md) — *revision*, *revision due*, and the counts a screen may not carry
- [Functional requirements](../requirements/functional.md) — FR-006's four criteria, two met in full, one partly, and one deferred
- [Coding standards](../development/coding-standards.md) — the UI responsibility rule that keeps the scheduling in the backend
- [Repository and folder structure](../development/folder-structure.md) — where the domain module, the route, and the feature live
- [Delivery milestones](../roadmap/milestones.md) — the Milestone 3 item this closes
- [Architecture decision register](../architecture/decisions.md) — DEC-040
